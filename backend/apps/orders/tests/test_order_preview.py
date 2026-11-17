"""结算预览：金额规则与下单前校验。"""

import pytest

from apps.cart.models import CartItem
from apps.catalog.models import Product, Sku
from apps.orders.tests.conftest import make_address, make_cart_item, make_sku

PREVIEW_URL = "/api/v1/orders/preview/"


def _preview(client, item_ids, address_public_id):
    return client.post(
        PREVIEW_URL,
        {"cart_item_public_ids": item_ids, "address_public_id": address_public_id},
        format="json",
    )


def test_preview_requires_auth(client, address, sku):
    response = client.post(PREVIEW_URL, {}, format="json")

    assert response.status_code == 401


def test_preview_free_shipping_and_snapshot(auth_client, user, address, sku):
    item = make_cart_item(user, sku, quantity=2)

    response = _preview(auth_client, [item.public_id], address.public_id)

    assert response.status_code == 200
    body = response.data
    assert body["items_amount"] == "198.00"
    assert body["discount_amount"] == "0.00"
    assert body["shipping_amount"] == "0.00"
    assert body["payable_amount"] == "198.00"
    assert body["free_shipping_threshold"] == "99.00"
    assert body["items"][0]["cart_item_public_id"] == item.public_id
    assert body["items"][0]["unit_price"] == "99.00"
    assert body["items"][0]["item_amount"] == "198.00"
    assert body["address"]["receiver_name"] == "张三"
    assert body["address"]["phone"] == "13800138000"


def test_preview_charges_shipping_below_threshold(auth_client, user, address, product):
    cheap_sku = make_sku(product, sku_code="CHEAP-001", sale_price="10.00")
    item = make_cart_item(user, cheap_sku, quantity=1)

    response = _preview(auth_client, [item.public_id], address.public_id)

    assert response.status_code == 200
    assert response.data["items_amount"] == "10.00"
    assert response.data["shipping_amount"] == "10.00"
    assert response.data["payable_amount"] == "20.00"


def test_preview_rejects_off_sale_product(auth_client, user, address, product):
    item = make_cart_item(user, make_sku(product), quantity=1)
    Product.objects.filter(pk=product.pk).update(status=Product.Status.OFF_SALE)

    response = _preview(auth_client, [item.public_id], address.public_id)

    assert response.status_code == 422
    assert response.data["code"] == "ORDER_STOCK_CHANGED"
    assert response.data["detail"]["reason"] == "商品已下架"


def test_preview_rejects_off_sale_sku(auth_client, user, address, product):
    sku = make_sku(product, status=Sku.Status.OFF_SALE)
    item = make_cart_item(user, sku, quantity=1)

    response = _preview(auth_client, [item.public_id], address.public_id)

    assert response.status_code == 422
    assert response.data["detail"]["reason"] == "规格已下架"


def test_preview_rejects_insufficient_available_stock(auth_client, user, address, product):
    sku = make_sku(product, stock=2)
    Sku.objects.filter(pk=sku.pk).update(locked_stock=2)
    item = make_cart_item(user, sku, quantity=1)

    response = _preview(auth_client, [item.public_id], address.public_id)

    assert response.status_code == 422
    assert response.data["detail"]["available"] == 0


def test_preview_rejects_deleted_sku(auth_client, user, address, product):
    sku = make_sku(product)
    item = make_cart_item(user, sku, quantity=1)
    Sku.objects.filter(pk=sku.pk).update(is_deleted=True)

    response = _preview(auth_client, [item.public_id], address.public_id)

    assert response.status_code == 422
    assert response.data["detail"]["reason"] == "商品已失效"


def test_preview_unknown_cart_item_returns_404(auth_client, address):
    response = _preview(auth_client, ["not-exists"], address.public_id)

    assert response.status_code == 404
    assert response.data["code"] == "CART_ITEM_NOT_FOUND"


def test_preview_cannot_use_other_users_cart_item(auth_client, other_user, address, sku):
    item = make_cart_item(other_user, sku, quantity=1)

    response = _preview(auth_client, [item.public_id], address.public_id)

    assert response.status_code == 404
    assert CartItem.objects.filter(pk=item.pk).exists()


def test_preview_cannot_use_other_users_address(auth_client, user, other_address, sku):
    item = make_cart_item(user, sku, quantity=1)

    response = _preview(auth_client, [item.public_id], other_address.public_id)

    assert response.status_code == 404
    assert response.data["code"] == "COMMON_NOT_FOUND"


def test_preview_rejects_empty_items(auth_client, address):
    response = _preview(auth_client, [], address.public_id)

    assert response.status_code == 400


@pytest.mark.parametrize("missing_field", ["cart_item_public_ids", "address_public_id"])
def test_preview_requires_fields(auth_client, address, sku, missing_field):
    payload = {
        "cart_item_public_ids": ["x"],
        "address_public_id": address.public_id,
    }
    payload.pop(missing_field)

    response = auth_client.post(PREVIEW_URL, payload, format="json")

    assert response.status_code == 400


def test_preview_ignores_unselected_items_only_by_explicit_ids(auth_client, user, address, sku):
    first = make_cart_item(user, sku, quantity=1)
    other_sku = make_sku(sku.product, sku_code="DRESS-002")
    make_cart_item(user, other_sku, quantity=5)

    response = _preview(auth_client, [first.public_id], address.public_id)

    assert response.status_code == 200
    assert len(response.data["items"]) == 1
    assert response.data["payable_amount"] == "99.00"


def test_preview_address_snapshot_is_decrypted(auth_client, user, product):
    address = make_address(user, receiver_name="王五", phone="13700137000")
    sku = make_sku(product, sale_price="120.00")
    item = make_cart_item(user, sku, quantity=1)

    response = _preview(auth_client, [item.public_id], address.public_id)

    assert response.status_code == 200
    assert response.data["address"]["phone"] == "13700137000"
    assert response.data["shipping_amount"] == "0.00"
