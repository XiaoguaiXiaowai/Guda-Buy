import uuid

import pytest

from apps.cart.models import CartItem
from apps.cart.tests.conftest import make_sku
from apps.catalog.models import Product, Sku

CART_URL = "/api/v1/cart/"
ITEMS_URL = "/api/v1/cart/items/"
CLEAR_URL = "/api/v1/cart/clear/"
COUNT_URL = "/api/v1/cart/count/"


def _add(client, sku, quantity=1):
    return client.post(
        ITEMS_URL, {"sku_public_id": sku.public_id, "quantity": quantity}, format="json"
    )


def test_cart_requires_auth(client):
    assert client.get(CART_URL).status_code == 401
    assert client.post(ITEMS_URL, {}, format="json").status_code == 401
    assert client.get(COUNT_URL).status_code == 401


def test_add_item_returns_amounts_as_string(auth_client, sku):
    response = _add(auth_client, sku, 2)

    assert response.status_code == 201
    assert response.data["quantity"] == 2
    assert response.data["sale_price"] == "99.00"
    assert response.data["subtotal"] == "198.00"
    assert response.data["status"] == "VALID"

    count = auth_client.get(COUNT_URL)
    assert count.data == {"count": 1, "total_quantity": 2}


def test_add_same_sku_merges_quantity(auth_client, user, sku):
    _add(auth_client, sku, 1)
    response = _add(auth_client, sku, 2)

    assert response.status_code == 201
    assert response.data["quantity"] == 3
    assert CartItem.objects.filter(user=user, sku=sku).count() == 1


def test_add_over_stock_returns_422(auth_client, product):
    sku = make_sku(product, stock=2)

    response = _add(auth_client, sku, 3)

    assert response.status_code == 422
    assert response.data["code"] == "CART_STOCK_NOT_ENOUGH"
    assert response.data["detail"]["available"] == 2
    assert CartItem.objects.count() == 0


def test_merge_over_stock_returns_422(auth_client, product):
    sku = make_sku(product, stock=2)
    _add(auth_client, sku, 2)

    response = _add(auth_client, sku, 1)

    assert response.status_code == 422
    assert response.data["code"] == "CART_STOCK_NOT_ENOUGH"
    assert CartItem.objects.get(sku=sku).quantity == 2


def test_add_off_sale_product_returns_invalid(auth_client, product):
    product.status = Product.Status.OFF_SALE
    product.save(update_fields=["status"])
    sku = make_sku(product)

    response = _add(auth_client, sku)

    assert response.status_code == 422
    assert response.data["code"] == "CART_ITEM_INVALID"


def test_add_off_sale_sku_returns_invalid(auth_client, product):
    sku = make_sku(product, status=Sku.Status.OFF_SALE)

    response = _add(auth_client, sku)

    assert response.status_code == 422
    assert response.data["code"] == "CART_ITEM_INVALID"


def test_add_unknown_sku_returns_404(auth_client):
    response = auth_client.post(
        ITEMS_URL, {"sku_public_id": "not-exists", "quantity": 1}, format="json"
    )

    assert response.status_code == 404
    assert response.data["code"] == "PRODUCT_SKU_NOT_FOUND"


@pytest.mark.parametrize("quantity", [0, 100])
def test_add_quantity_out_of_range_returns_400(auth_client, sku, quantity):
    assert _add(auth_client, sku, quantity).status_code == 400


def test_single_item_quantity_limit(auth_client, product):
    sku = make_sku(product, stock=200)
    _add(auth_client, sku, 99)

    response = _add(auth_client, sku, 1)

    assert response.status_code == 422
    assert response.data["code"] == "CART_ITEM_LIMIT"


def test_cart_item_limit_is_50(auth_client, user, product):
    skus = [make_sku(product, sku_code=f"DRESS-{index:03d}") for index in range(51)]
    CartItem.objects.bulk_create(
        [
            CartItem(user=user, sku=item, quantity=1, public_id=uuid.uuid4().hex)
            for item in skus[:50]
        ]
    )

    response = _add(auth_client, skus[50])

    assert response.status_code == 422
    assert response.data["code"] == "CART_ITEM_LIMIT"


def test_update_quantity_recalculates_subtotal(auth_client, sku):
    item = _add(auth_client, sku).data

    response = auth_client.patch(f"{ITEMS_URL}{item['public_id']}/", {"quantity": 3}, format="json")

    assert response.status_code == 200
    assert response.data["subtotal"] == "297.00"

    cart = auth_client.get(CART_URL)
    assert cart.data["summary"]["items_amount"] == "297.00"
    assert cart.data["summary"]["total_quantity"] == 3


def test_update_quantity_zero_deletes_item(auth_client, sku):
    item = _add(auth_client, sku).data

    response = auth_client.patch(f"{ITEMS_URL}{item['public_id']}/", {"quantity": 0}, format="json")

    assert response.status_code == 204
    assert CartItem.objects.count() == 0


def test_update_quantity_over_stock_returns_422(auth_client, product):
    sku = make_sku(product, stock=5)
    item = _add(auth_client, sku, 2).data

    response = auth_client.patch(f"{ITEMS_URL}{item['public_id']}/", {"quantity": 6}, format="json")

    assert response.status_code == 422
    assert response.data["code"] == "CART_STOCK_NOT_ENOUGH"


def test_selection_persisted_and_amount_only_counts_selected(auth_client, product):
    first = make_sku(product, sku_code="DRESS-001", sale_price="99.00")
    second = make_sku(product, sku_code="DRESS-002", sale_price="199.00", spec_text="黑色 / L")
    first_item = _add(auth_client, first, 1).data
    _add(auth_client, second, 1)

    response = auth_client.patch(
        f"{ITEMS_URL}{first_item['public_id']}/", {"is_selected": False}, format="json"
    )

    assert response.status_code == 200
    assert response.data["is_selected"] is False

    cart = auth_client.get(CART_URL)
    assert cart.data["summary"]["items_amount"] == "199.00"
    assert cart.data["summary"]["selected_count"] == 1
    assert cart.data["summary"]["can_checkout"] is True


def test_empty_cart_cannot_checkout(auth_client):
    cart = auth_client.get(CART_URL)

    assert cart.data["items"] == []
    assert cart.data["summary"] == {
        "items_count": 0,
        "total_quantity": 0,
        "selected_count": 0,
        "valid_count": 0,
        "items_amount": "0.00",
        "can_checkout": False,
    }


def test_unpublished_product_marked_invalid(auth_client, product, sku):
    _add(auth_client, sku, 2)
    product.status = Product.Status.OFF_SALE
    product.save(update_fields=["status"])

    cart = auth_client.get(CART_URL)

    item = cart.data["items"][0]
    assert item["status"] == "INVALID"
    assert item["status_text"] == "已失效"
    assert item["status_reason"] == "商品已下架"
    assert cart.data["summary"]["items_amount"] == "0.00"
    assert cart.data["summary"]["valid_count"] == 0
    assert cart.data["summary"]["can_checkout"] is False


def test_deleted_product_marked_invalid(auth_client, product, sku):
    _add(auth_client, sku)
    product.is_deleted = True
    product.save(update_fields=["is_deleted"])

    cart = auth_client.get(CART_URL)

    assert cart.data["items"][0]["status"] == "INVALID"
    assert cart.data["items"][0]["status_reason"] == "商品已失效"


def test_off_sale_sku_marked_invalid(auth_client, product, sku):
    _add(auth_client, sku)
    sku.status = Sku.Status.OFF_SALE
    sku.save(update_fields=["status"])

    cart = auth_client.get(CART_URL)

    assert cart.data["items"][0]["status"] == "INVALID"
    assert cart.data["items"][0]["status_reason"] == "规格已下架"


def test_stock_shortage_marked_insufficient(auth_client, product, sku):
    _add(auth_client, sku, 3)
    sku.stock = 1
    sku.save(update_fields=["stock"])

    cart = auth_client.get(CART_URL)

    item = cart.data["items"][0]
    assert item["status"] == "INSUFFICIENT"
    assert item["status_text"] == "库存不足"
    assert item["status_reason"] == "库存仅剩 1 件"
    assert cart.data["summary"]["items_amount"] == "0.00"
    assert cart.data["summary"]["can_checkout"] is False


def test_cross_user_cannot_modify_item(auth_client, other_client, sku):
    item = _add(auth_client, sku).data

    patch = other_client.patch(f"{ITEMS_URL}{item['public_id']}/", {"quantity": 5}, format="json")
    delete = other_client.delete(f"{ITEMS_URL}{item['public_id']}/")

    assert patch.status_code == 404
    assert delete.status_code == 404
    assert CartItem.objects.get(public_id=item["public_id"]).quantity == 1


def test_delete_item_is_idempotent_without_500(auth_client, sku):
    item = _add(auth_client, sku).data

    assert auth_client.delete(f"{ITEMS_URL}{item['public_id']}/").status_code == 204
    assert auth_client.delete(f"{ITEMS_URL}{item['public_id']}/").status_code == 404


def test_clear_only_selected(auth_client, product):
    first = make_sku(product, sku_code="DRESS-001")
    second = make_sku(product, sku_code="DRESS-002")
    third = make_sku(product, sku_code="DRESS-003")
    second_item = _add(auth_client, second).data
    _add(auth_client, first)
    _add(auth_client, third)
    auth_client.patch(
        f"{ITEMS_URL}{second_item['public_id']}/", {"is_selected": False}, format="json"
    )

    response = auth_client.post(CLEAR_URL, {"only_selected": True}, format="json")

    assert response.status_code == 200
    assert response.data["deleted"] == 2
    assert CartItem.objects.count() == 1
    assert CartItem.objects.get().public_id == second_item["public_id"]


def test_clear_all(auth_client, product):
    _add(auth_client, make_sku(product, sku_code="DRESS-001"))
    _add(auth_client, make_sku(product, sku_code="DRESS-002"))

    response = auth_client.post(CLEAR_URL, {}, format="json")

    assert response.status_code == 200
    assert response.data["deleted"] == 2
    assert CartItem.objects.count() == 0


def test_update_requires_at_least_one_field(auth_client, sku):
    item = _add(auth_client, sku).data

    response = auth_client.patch(f"{ITEMS_URL}{item['public_id']}/", {}, format="json")

    assert response.status_code == 400
