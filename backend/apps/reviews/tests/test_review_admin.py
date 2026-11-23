import logging

from apps.notifications.models import Notification
from apps.reviews.models import Review
from apps.reviews.tests.conftest import build_order, make_review

ADMIN_LIST_URL = "/api/v1/admin/reviews/"
APPROVE_URL = "/api/v1/admin/reviews/{public_id}/approve/"
REJECT_URL = "/api/v1/admin/reviews/{public_id}/reject/"


def test_admin_list_filters_and_payload(admin_client, user, address, sku):
    pending_order = build_order(user, address, sku)
    approved_order = build_order(user, address, sku)
    make_review(user, pending_order, sku)
    make_review(user, approved_order, sku, status=Review.Status.APPROVED, rating=4)

    response = admin_client.get(ADMIN_LIST_URL, {"status": "PENDING"})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    item = body["results"][0]
    assert item["status"] == Review.Status.PENDING
    assert item["order_no"] == pending_order.order_no
    assert item["user"]["username"] == user.username
    assert item["product"]["name"] == sku.product.name


def test_approve_publishes_review_and_notifies(
    admin_client, user, completed_order, sku, django_capture_on_commit_callbacks, caplog
):
    review = make_review(user, completed_order, sku)
    caplog.set_level(logging.INFO, logger="guda.reviews")

    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(APPROVE_URL.format(public_id=review.public_id))

    assert response.status_code == 200
    assert response.json()["status"] == Review.Status.APPROVED
    review.refresh_from_db()
    assert review.status == Review.Status.APPROVED

    notification = Notification.objects.get(user=user)
    assert notification.type == "SYSTEM"
    assert notification.biz_public_id == completed_order.order_no
    assert "通过" in notification.title
    assert any("reviews.approve" in record.getMessage() for record in caplog.records)


def test_reject_requires_reason_and_notifies(
    admin_client, user, completed_order, sku, django_capture_on_commit_callbacks
):
    review = make_review(user, completed_order, sku)
    url = REJECT_URL.format(public_id=review.public_id)

    assert admin_client.post(url, {}, format="json").status_code == 400

    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(url, {"reject_reason": "内容与商品无关"}, format="json")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == Review.Status.REJECTED
    assert body["reject_reason"] == "内容与商品无关"

    notification = Notification.objects.get(user=user)
    assert "未通过" in notification.title
    assert "内容与商品无关" in notification.content


def test_audit_only_pending_review(admin_client, user, address, sku, completed_order):
    review = make_review(user, completed_order, sku, status=Review.Status.APPROVED)
    second_order = build_order(user, address, sku)
    pending = make_review(user, second_order, sku)

    conflict = admin_client.post(APPROVE_URL.format(public_id=review.public_id))
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "REVIEW_STATUS_CONFLICT"

    assert admin_client.post(APPROVE_URL.format(public_id=pending.public_id)).status_code == 200
    second = admin_client.post(APPROVE_URL.format(public_id=pending.public_id))
    assert second.status_code == 409


def test_permissions(auth_client, client, review):
    assert auth_client.get(ADMIN_LIST_URL).status_code == 403
    assert auth_client.post(APPROVE_URL.format(public_id=review.public_id)).status_code == 403
    assert client.get(ADMIN_LIST_URL).status_code == 401


def test_operator_can_manage_reviews_but_not_submit_user_review(completed_order, review):
    from django.contrib.auth.models import Group
    from rest_framework.test import APIClient

    from apps.accounts.models import User

    operator = User.objects.create_user(
        username="review_operator",
        email="review_operator@example.com",
        password="Passw0rd123",
    )
    group, _ = Group.objects.get_or_create(name="operator")
    operator.groups.add(group)
    client = APIClient()
    client.force_authenticate(user=operator)

    assert client.get(ADMIN_LIST_URL).status_code == 200

    # 用户评价接口仅订单本人可用；越权统一以 404 隐藏资源存在性，比 403 更保守
    review_url = f"/api/v1/orders/{completed_order.order_no}/review/"
    assert client.get(review_url).status_code == 404
    assert (
        client.post(
            review_url, {"rating": 5, "content": "运营越权提交评价"}, format="json"
        ).status_code
        == 404
    )


def test_approval_refreshes_product_detail_summary(
    admin_client, user, completed_order, sku, django_capture_on_commit_callbacks
):
    product_url = f"/api/v1/products/{sku.product.public_id}/"
    make_review(user, completed_order, sku, rating=5)

    before = admin_client.get(product_url).json()
    assert before["review_summary"]["count"] == 0

    review = Review.objects.get(order=completed_order)
    with django_capture_on_commit_callbacks(execute=True):
        assert admin_client.post(APPROVE_URL.format(public_id=review.public_id)).status_code == 200

    after = admin_client.get(product_url).json()
    assert after["review_summary"]["count"] == 1
    assert after["review_summary"]["average"] == "5.0"
