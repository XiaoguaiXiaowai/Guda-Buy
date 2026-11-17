"""并发下单：库存锁定必须防止超卖。"""

from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connections

from apps.accounts.models import User
from apps.catalog.models import Category, Product
from apps.common.exceptions import BusinessError
from apps.orders import services
from apps.orders.models import Order
from apps.orders.tests.conftest import make_address, make_cart_item, make_sku


def _place_order(user, item_public_id, address_public_id, key):
    try:
        services.create_order(
            user,
            cart_item_public_ids=[item_public_id],
            address_public_id=address_public_id,
            remark="",
            idempotency_key=key,
        )
        return "ok"
    except BusinessError as exc:
        return exc.code
    finally:
        connections.close_all()


@pytest.mark.django_db(transaction=True)
def test_concurrent_orders_never_oversell():
    category = Category.objects.create(name="并发测试", sort_weight=1)
    product = Product.objects.create(
        category=category,
        name="限量款",
        status=Product.Status.ON_SALE,
        price_min="99.00",
        price_max="99.00",
    )
    sku = make_sku(product, sku_code="LIMITED-001", stock=10, sale_price="99.00")

    users = [
        User.objects.create_user(
            username=f"race_user_{index}",
            email=f"race_{index}@example.com",
            password="Passw0rd123",
        )
        for index in range(20)
    ]
    tasks = []
    for index, user in enumerate(users):
        address = make_address(user, phone=f"1380013{index:04d}", is_default=True)
        item = make_cart_item(user, sku, quantity=1)
        tasks.append((user, item.public_id, address.public_id, f"race-key-{index}"))

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda args: _place_order(*args), tasks))

    assert results.count("ok") == 10
    assert results.count("ORDER_STOCK_CHANGED") == 10
    assert Order.objects.count() == 10
    sku.refresh_from_db()
    assert sku.locked_stock == 10
