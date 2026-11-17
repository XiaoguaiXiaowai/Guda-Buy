"""下单：事务、快照、库存锁定、购物车清理与幂等。"""

import re
import uuid
from decimal import Decimal

from apps.cart.models import CartItem
from apps.catalog.models import Sku
from apps.orders.models import Order
from apps.orders.tests.conftest import make_cart_item, make_sku
from apps.payments.models import Payment

ORDERS_URL = "/api/v1/orders/"


def _create(client, item_ids, address_public_id, *, key=None, remark="", extra=None):
    payload = {
        "cart_item_public_ids": item_ids,
        "address_public_id": address_public_id,
        "remark": remark,
    }
    if extra:
        payload.update(extra)
    headers = {"HTTP_IDEMPOTENCY_KEY": key or uuid.uuid4().hex}
    return client.post(ORDERS_URL, payload, format="json", **headers)


def test_create_order_requires_auth(client, address, sku):
    response = client.post(ORDERS_URL, {}, format="json")

    assert response.status_code == 401


def test_create_order_success_snapshots_and_locks(auth_client, user, address, sku):
    item = make_cart_item(user, sku, quantity=2)

    response = _create(auth_client, [item.public_id], address.public_id, remark="  尽快发货  ")

    assert response.status_code == 201
    body = response.data
    assert re.fullmatch(r"GD\d{18}", body["order_no"])
    assert body["status"] == "PENDING_PAYMENT"
    assert body["status_text"] == "待支付"
    assert body["items_amount"] == "198.00"
    assert body["shipping_amount"] == "0.00"
    assert body["payable_amount"] == "198.00"
    assert body["can_pay"] is True
    assert body["can_cancel"] is True
    assert body["can_confirm"] is False
    assert body["items"][0]["product_name"] == "法式碎花连衣裙"
    assert body["items"][0]["sku_spec"] == "米白 / M"
    assert body["items"][0]["quantity"] == 2
    assert body["address"]["receiver_name"] == "张三"
    assert body["address"]["phone"] == "13800138000"
    assert body["remark"] == "尽快发货"
    assert body["payments"][0]["status"] == "PENDING"
    assert body["payments"][0]["amount"] == "198.00"
    assert [log["to_status"] for log in body["status_logs"]] == ["PENDING_PAYMENT"]

    order = Order.objects.get(order_no=body["order_no"])
    assert order.user == user
    assert order.items.count() == 1
    assert order.items.first().unit_price == Decimal("99.00")
    sku.refresh_from_db()
    assert sku.locked_stock == 2
    assert Payment.objects.filter(order=order, status=Payment.Status.PENDING).count() == 1
    assert not CartItem.objects.filter(pk=item.pk).exists()
    assert 25 <= (order.pay_expires_at - order.created_at).total_seconds() / 60 <= 35


def test_create_order_locks_only_selected_items(auth_client, user, address, sku):
    selected = make_cart_item(user, sku, quantity=1)
    other_sku = make_sku(sku.product, sku_code="DRESS-002")
    kept = make_cart_item(user, other_sku, quantity=1)

    response = _create(auth_client, [selected.public_id], address.public_id)

    assert response.status_code == 201
    assert not CartItem.objects.filter(pk=selected.pk).exists()
    assert CartItem.objects.filter(pk=kept.pk).exists()
    other_sku.refresh_from_db()
    assert other_sku.locked_stock == 0


def test_create_order_is_idempotent_for_same_key_and_payload(auth_client, user, address, sku):
    item = make_cart_item(user, sku, quantity=2)
    key = "idem-key-001"

    first = _create(auth_client, [item.public_id], address.public_id, key=key)
    second = _create(auth_client, [item.public_id], address.public_id, key=key)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.data["order_no"] == second.data["order_no"]
    assert Order.objects.filter(user=user).count() == 1
    sku.refresh_from_db()
    assert sku.locked_stock == 2


def test_create_order_rejects_same_key_with_different_payload(
    auth_client, user, address, other_address, sku
):
    item = make_cart_item(user, sku, quantity=1)
    key = "idem-key-conflict"

    first = _create(auth_client, [item.public_id], address.public_id, key=key)
    second = _create(auth_client, [item.public_id], other_address.public_id, key=key)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.data["code"] == "ORDER_IDEMPOTENT_REPLAY"


def test_create_order_missing_idempotency_key(auth_client, user, address, sku):
    item = make_cart_item(user, sku)

    response = auth_client.post(
        ORDERS_URL,
        {"cart_item_public_ids": [item.public_id], "address_public_id": address.public_id},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "COMMON_VALIDATION_ERROR"


def test_create_order_rejects_overlong_idempotency_key(auth_client, user, address, sku):
    item = make_cart_item(user, sku)

    response = _create(auth_client, [item.public_id], address.public_id, key="k" * 65)

    assert response.status_code == 400
    assert response.data["code"] == "COMMON_VALIDATION_ERROR"


def test_create_order_stock_changed_rolls_back(auth_client, user, address, sku):
    item = make_cart_item(user, sku, quantity=2)
    Sku.objects.filter(pk=sku.pk).update(locked_stock=9)

    response = _create(auth_client, [item.public_id], address.public_id)

    assert response.status_code == 422
    assert response.data["code"] == "ORDER_STOCK_CHANGED"
    assert Order.objects.count() == 0
    assert CartItem.objects.filter(pk=item.pk).exists()
    sku.refresh_from_db()
    assert sku.locked_stock == 9


def test_create_order_rejects_unknown_cart_item(auth_client, address):
    response = _create(auth_client, ["not-exists"], address.public_id)

    assert response.status_code == 404
    assert response.data["code"] == "CART_ITEM_NOT_FOUND"


def test_create_order_rejects_other_users_address(auth_client, user, other_address, sku):
    item = make_cart_item(user, sku)

    response = _create(auth_client, [item.public_id], other_address.public_id)

    assert response.status_code == 404
    assert Order.objects.count() == 0


def test_create_order_shipping_below_threshold(auth_client, user, address, product):
    sku = make_sku(product, sku_code="CHEAP-002", sale_price="30.00")
    item = make_cart_item(user, sku, quantity=2)

    response = _create(auth_client, [item.public_id], address.public_id)

    assert response.status_code == 201
    assert response.data["items_amount"] == "60.00"
    assert response.data["shipping_amount"] == "10.00"
    assert response.data["payable_amount"] == "70.00"


def test_order_detail_keeps_snapshot_after_catalog_change(auth_client, user, address, sku):
    item = make_cart_item(user, sku, quantity=1)
    created = _create(auth_client, [item.public_id], address.public_id)
    order_no = created.data["order_no"]

    sku.sale_price = Decimal("199.00")
    sku.save(update_fields=["sale_price"])
    sku.product.name = "改名后的商品"
    sku.product.save(update_fields=["name"])

    response = auth_client.get(f"/api/v1/orders/{order_no}/")

    assert response.status_code == 200
    assert response.data["items"][0]["product_name"] == "法式碎花连衣裙"
    assert response.data["items"][0]["unit_price"] == "99.00"
    assert response.data["payable_amount"] == "99.00"
