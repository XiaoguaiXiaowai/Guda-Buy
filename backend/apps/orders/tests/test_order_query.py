"""订单列表、详情、取消与确认收货。"""

from decimal import Decimal

from apps.catalog.models import Product
from apps.orders.models import Order
from apps.orders.tests.conftest import build_order, make_sku
from apps.payments.models import Payment

ORDERS_URL = "/api/v1/orders/"


def test_order_list_requires_auth(client):
    assert client.get(ORDERS_URL).status_code == 401


def test_order_list_only_returns_own_orders(auth_client, user, other_user, address, sku):
    mine = build_order(user, address, sku, status=Order.Status.PENDING_PAYMENT)
    build_order(other_user, address, sku, status=Order.Status.CANCELLED)

    response = auth_client.get(ORDERS_URL)

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["order_no"] == mine.order_no
    assert response.data["results"][0]["total_quantity"] == 1


def test_order_list_filters_status_and_order_no(auth_client, user, address, sku):
    pending = build_order(user, address, sku, status=Order.Status.PENDING_PAYMENT)
    build_order(user, address, sku, status=Order.Status.CANCELLED)

    by_status = auth_client.get(ORDERS_URL, {"status": "PENDING_PAYMENT"})
    by_keyword = auth_client.get(ORDERS_URL, {"order_no": pending.order_no[:10]})
    invalid = auth_client.get(ORDERS_URL, {"status": "NOT_A_STATUS"})

    assert by_status.data["count"] == 1
    assert by_status.data["results"][0]["order_no"] == pending.order_no
    assert by_keyword.data["count"] == 1
    assert invalid.data["count"] == 2


def test_order_list_pagination(auth_client, user, address, sku):
    for _ in range(3):
        build_order(user, address, sku)

    response = auth_client.get(ORDERS_URL, {"page": 1, "page_size": 2})

    assert response.status_code == 200
    assert response.data["count"] == 3
    assert response.data["page"] == 1
    assert response.data["page_size"] == 2
    assert response.data["total_pages"] == 2
    assert len(response.data["results"]) == 2


def test_order_detail_returns_full_payload(auth_client, user, address, sku):
    order = build_order(user, address, sku, status=Order.Status.PENDING_PAYMENT)

    response = auth_client.get(f"/api/v1/orders/{order.order_no}/")

    assert response.status_code == 200
    body = response.data
    assert body["order_no"] == order.order_no
    assert body["address"]["province"] == "浙江省"
    assert body["items"][0]["sku_spec"] == "米白 / M"
    assert body["discount_amount"] == "0.00"
    assert body["shipping_amount"] == "0.00"
    assert body["payments"][0]["payment_no"] == order.payments.first().payment_no
    assert body["status_logs"][0]["to_status"] == "PENDING_PAYMENT"
    assert body["tracking_no"] == ""


def test_order_detail_cannot_read_other_users_order(auth_client, other_user, address, sku):
    order = build_order(other_user, address, sku)

    response = auth_client.get(f"/api/v1/orders/{order.order_no}/")

    assert response.status_code == 404
    assert response.data["code"] == "ORDER_NOT_FOUND"


def test_order_detail_not_found(auth_client):
    response = auth_client.get("/api/v1/orders/GD-NOT-EXISTS/")

    assert response.status_code == 404


def test_cancel_order_releases_locked_stock_once(auth_client, user, address, sku):
    order = build_order(user, address, sku, quantity=2, lock_stock=True)
    sku.refresh_from_db()
    assert sku.locked_stock == 2

    first = auth_client.post(f"/api/v1/orders/{order.order_no}/cancel/")
    second = auth_client.post(f"/api/v1/orders/{order.order_no}/cancel/")

    assert first.status_code == 200
    assert first.data["status"] == "CANCELLED"
    assert first.data["cancel_reason"] == "用户取消"
    assert first.data["cancelled_at"] is not None
    order.refresh_from_db()
    assert order.status == Order.Status.CANCELLED
    assert order.status_logs.last().to_status == Order.Status.CANCELLED
    assert order.payments.get().status == Payment.Status.CLOSED
    sku.refresh_from_db()
    assert sku.locked_stock == 0

    assert second.status_code == 409
    assert second.data["code"] == "ORDER_STATUS_CONFLICT"
    sku.refresh_from_db()
    assert sku.locked_stock == 0


def test_cancel_rejects_non_pending_order(auth_client, user, address, sku):
    order = build_order(user, address, sku, status=Order.Status.PAID)

    response = auth_client.post(f"/api/v1/orders/{order.order_no}/cancel/")

    assert response.status_code == 409


def test_cancel_cannot_cancel_other_users_order(auth_client, other_user, address, sku):
    order = build_order(other_user, address, sku)

    response = auth_client.post(f"/api/v1/orders/{order.order_no}/cancel/")

    assert response.status_code == 404


def test_confirm_order_completes_and_increases_sales_once(auth_client, user, address, sku):
    order = build_order(user, address, sku, status=Order.Status.SHIPPED, quantity=3)
    assert Product.objects.get(pk=sku.product_id).sales_count == 0

    first = auth_client.post(f"/api/v1/orders/{order.order_no}/confirm/")
    second = auth_client.post(f"/api/v1/orders/{order.order_no}/confirm/")

    assert first.status_code == 200
    assert first.data["status"] == "COMPLETED"
    assert first.data["completed_at"] is not None
    order.refresh_from_db()
    assert order.status_logs.last().to_status == Order.Status.COMPLETED
    assert Product.objects.get(pk=sku.product_id).sales_count == 3

    assert second.status_code == 409
    assert Product.objects.get(pk=sku.product_id).sales_count == 3


def test_confirm_sums_sales_across_skus_of_same_product(auth_client, user, address, sku):
    other_sku = make_sku(sku.product, sku_code="DRESS-009", sale_price="50.00")
    order = build_order(user, address, sku, status=Order.Status.SHIPPED, quantity=2)
    order.items.create(
        sku=other_sku,
        product_name=other_sku.product.name,
        sku_spec=other_sku.spec_text,
        main_image="",
        unit_price=Decimal("50.00"),
        quantity=1,
        item_amount=Decimal("50.00"),
    )

    response = auth_client.post(f"/api/v1/orders/{order.order_no}/confirm/")

    assert response.status_code == 200
    assert Product.objects.get(pk=sku.product_id).sales_count == 3


def test_confirm_rejects_unshipped_order(auth_client, user, address, sku):
    order = build_order(user, address, sku, status=Order.Status.PAID)

    response = auth_client.post(f"/api/v1/orders/{order.order_no}/confirm/")

    assert response.status_code == 409


def test_confirm_cannot_confirm_other_users_order(auth_client, other_user, address, sku):
    order = build_order(other_user, address, sku, status=Order.Status.SHIPPED)

    response = auth_client.post(f"/api/v1/orders/{order.order_no}/confirm/")

    assert response.status_code == 404


def test_address_referenced_by_unfinished_order_cannot_be_deleted(auth_client, user, address, sku):
    order = build_order(user, address, sku, status=Order.Status.PENDING_PAYMENT)

    blocked = auth_client.delete(f"/api/v1/users/me/addresses/{address.public_id}/")

    assert blocked.status_code == 422
    assert blocked.data["code"] == "USER_ADDRESS_IN_USE"

    auth_client.post(f"/api/v1/orders/{order.order_no}/cancel/")
    deleted = auth_client.delete(f"/api/v1/users/me/addresses/{address.public_id}/")
    assert deleted.status_code == 204


def test_address_deletable_after_order_completed(auth_client, user, address, sku):
    build_order(user, address, sku, status=Order.Status.COMPLETED)

    response = auth_client.delete(f"/api/v1/users/me/addresses/{address.public_id}/")

    assert response.status_code == 204
