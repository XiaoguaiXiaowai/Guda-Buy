from apps.reviews.models import Review
from apps.reviews.tests.conftest import build_order, make_review

REVIEW_URL = "/api/v1/orders/{order_no}/review/"


def test_eligibility_for_completed_order(auth_client, completed_order):
    response = auth_client.get(REVIEW_URL.format(order_no=completed_order.order_no))

    assert response.status_code == 200
    body = response.json()
    assert body["can_review"] is True
    assert body["reason"] == ""
    assert body["review"] is None
    assert body["window_expires_at"] is not None


def test_submit_review_creates_pending(auth_client, completed_order):
    response = auth_client.post(
        REVIEW_URL.format(order_no=completed_order.order_no),
        {"rating": 5, "content": "面料很舒服，版型也很好看", "is_anonymous": False},
        format="json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["review"]["status"] == Review.Status.PENDING
    assert body["can_review"] is False
    assert body["reason"] == "评价待审核"
    assert Review.objects.filter(order=completed_order).count() == 1


def test_uncompleted_order_cannot_review(auth_client, user, address, sku):
    from apps.orders.models import Order

    order = build_order(user, address, sku, status=Order.Status.PENDING_PAYMENT)

    response = auth_client.post(
        REVIEW_URL.format(order_no=order.order_no),
        {"rating": 5, "content": "提前评价测试内容"},
        format="json",
    )

    assert response.status_code == 422
    assert response.json()["code"] == "REVIEW_ORDER_NOT_COMPLETED"
    assert auth_client.get(REVIEW_URL.format(order_no=order.order_no)).json()["can_review"] is False


def test_review_window_expired(auth_client, user, address, sku):
    order = build_order(user, address, sku, completed_days_ago=8)

    response = auth_client.post(
        REVIEW_URL.format(order_no=order.order_no),
        {"rating": 4, "content": "超过七天再评价的内容"},
        format="json",
    )

    assert response.status_code == 422
    assert response.json()["code"] == "REVIEW_WINDOW_EXPIRED"


def test_duplicate_review_returns_conflict(auth_client, completed_order):
    payload = {"rating": 5, "content": "第一次提交的评价内容"}
    url = REVIEW_URL.format(order_no=completed_order.order_no)

    assert auth_client.post(url, payload, format="json").status_code == 201
    second = auth_client.post(url, payload, format="json")

    assert second.status_code == 409
    assert second.json()["code"] == "REVIEW_ALREADY_EXISTS"


def test_rejected_review_can_be_resubmitted(auth_client, user, completed_order, sku):
    make_review(
        user,
        completed_order,
        sku,
        status=Review.Status.REJECTED,
        rating=2,
        content="原评价内容不符合规范",
        reject_reason="内容过于简单",
    )

    response = auth_client.post(
        REVIEW_URL.format(order_no=completed_order.order_no),
        {"rating": 4, "content": "补充细节后重新提交的评价内容"},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()["review"]
    assert body["status"] == Review.Status.PENDING
    assert body["rating"] == 4
    assert body["reject_reason"] == ""
    assert Review.objects.filter(order=completed_order).count() == 1


def test_other_user_cannot_access_order(other_client, completed_order):
    url = REVIEW_URL.format(order_no=completed_order.order_no)

    assert other_client.get(url).status_code == 404
    assert (
        other_client.post(url, {"rating": 5, "content": "越权提交评价"}, format="json").status_code
        == 404
    )


def test_validation_of_rating_and_content(auth_client, completed_order):
    url = REVIEW_URL.format(order_no=completed_order.order_no)

    assert (
        auth_client.post(url, {"rating": 0, "content": "评分越界内容"}, format="json").status_code
        == 400
    )
    assert (
        auth_client.post(url, {"rating": 6, "content": "评分越界内容"}, format="json").status_code
        == 400
    )
    assert auth_client.post(url, {"rating": 5, "content": "太短"}, format="json").status_code == 400


def test_submit_requires_authentication(client, completed_order):
    url = REVIEW_URL.format(order_no=completed_order.order_no)
    assert (
        client.post(url, {"rating": 5, "content": "未登录提交内容"}, format="json").status_code
        == 401
    )


def test_sensitive_word_review_goes_to_manual_review(
    auth_client, completed_order, settings, caplog
):
    import logging

    settings.REVIEW_SENSITIVE_WORDS = ["代购"]
    caplog.set_level(logging.WARNING, logger="guda.reviews")

    response = auth_client.post(
        REVIEW_URL.format(order_no=completed_order.order_no),
        {"rating": 5, "content": "这条评价包含代购引流内容"},
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["review"]["status"] == Review.Status.PENDING
    assert any("敏感词" in record.getMessage() for record in caplog.records)


def test_multi_item_order_requires_sku(auth_client, user, address, sku):
    from apps.catalog.models import Product

    other_sku = sku.__class__.objects.create(
        product=Product.objects.create(
            category=sku.product.category,
            name="通勤西装",
            status=Product.Status.ON_SALE,
            price_min="199.00",
            price_max="199.00",
        ),
        sku_code="SUIT-001",
        spec_text="藏青 / L",
        specs={"颜色": "藏青", "尺码": "L"},
        sale_price="199.00",
        stock=5,
        stock_capacity=50,
    )
    order = build_order(user, address, sku)
    from apps.orders.models import OrderItem

    OrderItem.objects.create(
        order=order,
        sku=other_sku,
        product_name=other_sku.product.name,
        sku_spec=other_sku.spec_text,
        main_image=other_sku.product.main_image,
        unit_price=other_sku.sale_price,
        quantity=1,
        item_amount=other_sku.sale_price,
    )
    url = REVIEW_URL.format(order_no=order.order_no)

    missing = auth_client.post(url, {"rating": 5, "content": "多商品订单未指定商品"}, format="json")
    assert missing.status_code == 400

    selected = auth_client.post(
        url,
        {"rating": 5, "content": "多商品订单指定评价商品", "sku_public_id": other_sku.public_id},
        format="json",
    )
    assert selected.status_code == 201
