from decimal import Decimal

import pytest
from django.core.cache import caches
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import Category, Product, Sku


@pytest.fixture(autouse=True)
def clear_cache():
    caches["default"].clear()
    yield
    caches["default"].clear()


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="cart_user",
        email="cart_user@example.com",
        password="Passw0rd123",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="cart_other",
        email="cart_other@example.com",
        password="Passw0rd123",
    )


@pytest.fixture
def auth_client(client, user):
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def other_client(other_user):
    client = APIClient()
    client.force_authenticate(user=other_user)
    return client


@pytest.fixture
def category(db):
    return Category.objects.create(name="女装", sort_weight=10)


@pytest.fixture
def product(category):
    return Product.objects.create(
        category=category,
        name="法式碎花连衣裙",
        status=Product.Status.ON_SALE,
        price_min=Decimal("99.00"),
        price_max=Decimal("99.00"),
    )


def make_sku(product, *, sku_code="DRESS-001", stock=10, sale_price="99.00", **kwargs):
    return Sku.objects.create(
        product=product,
        sku_code=sku_code,
        spec_text=kwargs.pop("spec_text", "米白 / M"),
        specs=kwargs.pop("specs", {"颜色": "米白", "尺码": "M"}),
        sale_price=Decimal(sale_price),
        stock=stock,
        stock_capacity=kwargs.pop("stock_capacity", 100),
        **kwargs,
    )


@pytest.fixture
def sku(product):
    return make_sku(product)
