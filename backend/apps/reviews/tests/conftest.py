import uuid
from decimal import Decimal

import pytest
from django.core.cache import caches
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Address, User
from apps.catalog.models import Category, Product, Sku
from apps.orders.models import Order, OrderItem
from apps.reviews.models import Review


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
        username="review_user",
        email="review_user@example.com",
        password="Passw0rd123",
        nickname="张小明",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="review_other",
        email="review_other@example.com",
        password="Passw0rd123",
        nickname="李四",
    )


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def other_client(other_user):
    client = APIClient()
    client.force_authenticate(user=other_user)
    return client


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="review_admin",
        email="review_admin@example.com",
        password="Passw0rd123",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
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


def make_sku(product, *, sku_code="DRESS-001", spec_text="米白 / M"):
    return Sku.objects.create(
        product=product,
        sku_code=sku_code,
        spec_text=spec_text,
        specs={"颜色": "米白", "尺码": "M"},
        sale_price=Decimal("99.00"),
        stock=10,
        stock_capacity=100,
    )


@pytest.fixture
def sku(product):
    return make_sku(product)


@pytest.fixture
def address(user):
    return Address.objects.create(
        user=user,
        receiver_name="张三",
        province="浙江省",
        city="杭州市",
        district="西湖区",
        detail="文三路 100 号",
        postal_code="310012",
        is_default=True,
    )


def build_order(
    user,
    address,
    sku,
    *,
    status=Order.Status.COMPLETED,
    completed_days_ago=1,
    quantity=1,
):
    unit_price = sku.sale_price
    amount = unit_price * quantity
    now = timezone.now()
    completed_at = (
        now - timezone.timedelta(days=completed_days_ago)
        if status == Order.Status.COMPLETED
        else None
    )
    order = Order.objects.create(
        order_no="GD" + uuid.uuid4().hex[:18].upper(),
        user=user,
        status=status,
        items_amount=amount,
        discount_amount=Decimal("0.00"),
        shipping_amount=Decimal("0.00"),
        payable_amount=amount,
        address_snapshot={"receiver_name": address.receiver_name},
        address_public_id=address.public_id,
        pay_expires_at=now + timezone.timedelta(minutes=30),
        shipped_at=now - timezone.timedelta(days=2),
        completed_at=completed_at,
        idempotency_request_hash="",
    )
    OrderItem.objects.create(
        order=order,
        sku=sku,
        product_name=sku.product.name,
        sku_spec=sku.spec_text,
        main_image=sku.product.main_image,
        unit_price=unit_price,
        quantity=quantity,
        item_amount=amount,
    )
    return order


@pytest.fixture
def completed_order(user, address, sku):
    return build_order(user, address, sku)


def make_review(user, order, sku, *, status=Review.Status.PENDING, **kwargs):
    return Review.objects.create(
        order=order,
        user=user,
        product=sku.product,
        sku=sku,
        rating=kwargs.pop("rating", 5),
        content=kwargs.pop("content", "面料很舒服，版型也很好看"),
        status=status,
        **kwargs,
    )


@pytest.fixture
def review(user, completed_order, sku):
    return make_review(user, completed_order, sku)
