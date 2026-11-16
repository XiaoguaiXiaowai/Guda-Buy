import io
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, Permission
from django.core.cache import caches
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
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
def customer(db):
    return User.objects.create_user(
        username="catalog_customer",
        email="catalog_customer@example.com",
        password="Passw0rd123",
    )


@pytest.fixture
def operator(db):
    group, _ = Group.objects.get_or_create(name="operator")
    group.permissions.add(
        Permission.objects.get(content_type__app_label="catalog", codename="change_stock")
    )
    user = User.objects.create_user(
        username="catalog_operator",
        email="catalog_operator@example.com",
        password="Passw0rd123",
    )
    user.groups.add(group)
    return user


@pytest.fixture
def operator_client(client, operator):
    client.force_authenticate(user=operator)
    return client


@pytest.fixture
def parent_category(db):
    return Category.objects.create(name="女装", sort_weight=10)


@pytest.fixture
def child_category(db, parent_category):
    return Category.objects.create(name="连衣裙", parent=parent_category, sort_weight=1)


def make_product(category, *, name="法式碎花连衣裙", status=Product.Status.ON_SALE, **kwargs):
    defaults = {
        "subtitle": "春季新品",
        "description": "柔软面料",
        "price_min": Decimal("99.00"),
        "price_max": Decimal("129.00"),
        "sales_count": 0,
        "sort_weight": 0,
    }
    defaults.update(kwargs)
    return Product.objects.create(category=category, name=name, status=status, **defaults)


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
def product(db, child_category):
    return make_product(child_category)


@pytest.fixture
def sku(product):
    return make_sku(product)


def png_upload(name="cover.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), color=(255, 255, 255)).save(buffer, format="PNG")
    content_type = "image/gif" if name.endswith(".gif") else "image/png"
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)
