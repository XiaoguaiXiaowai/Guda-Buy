import uuid
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Address, User
from apps.catalog.models import Category, Product, Sku
from apps.orders.models import Order, OrderItem


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="support_customer",
        email="support_customer@example.com",
        password="Passw0rd123",
        nickname="王小明",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="support_other",
        email="support_other@example.com",
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


def make_support_user(username: str, nickname: str) -> User:
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="Passw0rd123",
        nickname=nickname,
    )
    group, _ = Group.objects.get_or_create(name="support")
    user.groups.add(group)
    return user


@pytest.fixture
def support_user(db):
    return make_support_user("support_agent", "客服小美")


@pytest.fixture
def other_support_user(db):
    return make_support_user("support_agent_two", "客服小刚")


@pytest.fixture
def support_client(support_user):
    client = APIClient()
    client.force_authenticate(user=support_user)
    return client


@pytest.fixture
def other_support_client(other_support_user):
    client = APIClient()
    client.force_authenticate(user=other_support_user)
    return client


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="support_admin",
        email="support_admin@example.com",
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


@pytest.fixture
def sku(product):
    return Sku.objects.create(
        product=product,
        sku_code="DRESS-001",
        spec_text="米白 / M",
        specs={"颜色": "米白", "尺码": "M"},
        sale_price=Decimal("99.00"),
        stock=10,
        stock_capacity=100,
    )


@pytest.fixture
def address(user):
    return Address.objects.create(
        user=user,
        receiver_name="王小明",
        province="浙江省",
        city="杭州市",
        district="西湖区",
        detail="文三路 100 号",
        postal_code="310012",
        is_default=True,
    )


@pytest.fixture
def order(user, address, sku):
    now = timezone.now()
    amount = sku.sale_price
    order = Order.objects.create(
        order_no="GD" + uuid.uuid4().hex[:18].upper(),
        user=user,
        status=Order.Status.PAID,
        items_amount=amount,
        discount_amount=Decimal("0.00"),
        shipping_amount=Decimal("0.00"),
        payable_amount=amount,
        address_snapshot={"receiver_name": address.receiver_name},
        address_public_id=address.public_id,
        pay_expires_at=now + timezone.timedelta(minutes=30),
        paid_at=now,
        idempotency_request_hash="",
    )
    OrderItem.objects.create(
        order=order,
        sku=sku,
        product_name=sku.product.name,
        sku_spec=sku.spec_text,
        main_image=sku.product.main_image,
        unit_price=amount,
        quantity=1,
        item_amount=amount,
    )
    return order
