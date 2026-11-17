"""支付测试夹具：待支付订单（已锁库存）与各角色客户端。"""

import uuid
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, Permission
from django.core.cache import caches
from django.db.models import F
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import Category, Product, Sku
from apps.orders.models import Order, OrderItem, OrderStatusLog
from apps.orders.tests.conftest import make_address
from apps.payments.models import Payment


@pytest.fixture(autouse=True)
def payment_settings(settings):
    settings.PAYMENT_CALLBACK_SECRET = "test-pay-secret"
    return settings


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
        username="pay_user",
        email="pay_user@example.com",
        password="Passw0rd123",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="pay_other",
        email="pay_other@example.com",
        password="Passw0rd123",
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
    return make_address(user)


def make_order(
    user,
    address,
    sku,
    *,
    status=Order.Status.PENDING_PAYMENT,
    quantity=2,
    pay_expires_minutes=30,
    channel=Payment.Channel.ALIPAY_MOCK,
):
    """构造订单：默认 2 件、锁定库存 2，并生成一张 PENDING 支付单。"""
    unit_price = sku.sale_price
    items_amount = unit_price * quantity
    order = Order.objects.create(
        order_no="GD" + uuid.uuid4().hex[:18].upper(),
        user=user,
        status=status,
        items_amount=items_amount,
        discount_amount=Decimal("0.00"),
        shipping_amount=Decimal("0.00"),
        payable_amount=items_amount,
        address_snapshot={
            "address_public_id": address.public_id,
            "receiver_name": address.receiver_name,
            "phone": address.phone,
            "province": address.province,
            "city": address.city,
            "district": address.district,
            "detail": address.detail,
            "postal_code": address.postal_code,
        },
        address_public_id=address.public_id,
        pay_expires_at=timezone.now() + timezone.timedelta(minutes=pay_expires_minutes),
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
        item_amount=items_amount,
    )
    OrderStatusLog.objects.create(
        order=order, from_status="", to_status=status, operator=user, remark="测试构造"
    )
    Payment.objects.create(
        payment_no="PAY" + uuid.uuid4().hex[:21].upper(),
        order=order,
        channel=channel,
        amount=order.payable_amount,
        status=Payment.Status.PENDING,
    )
    Sku.objects.filter(pk=sku.pk).update(locked_stock=F("locked_stock") + quantity)
    sku.refresh_from_db()
    return order


@pytest.fixture
def order(user, address, sku):
    return make_order(user, address, sku)


@pytest.fixture
def pending_payment(order):
    return order.payments.get(status=Payment.Status.PENDING)


@pytest.fixture
def operator_user(db):
    user = User.objects.create_user(
        username="pay_operator",
        email="pay_operator@example.com",
        password="Passw0rd123",
        is_staff=True,
    )
    group = Group.objects.create(name="operator")
    group.permissions.add(Permission.objects.get(codename="view_payment"))
    user.groups.add(group)
    return user


@pytest.fixture
def support_user(db):
    user = User.objects.create_user(
        username="pay_support",
        email="pay_support@example.com",
        password="Passw0rd123",
        is_staff=True,
    )
    user.groups.add(Group.objects.create(name="support"))
    return user


@pytest.fixture
def operator_client(operator_user):
    client = APIClient()
    client.force_authenticate(user=operator_user)
    return client


@pytest.fixture
def support_client(support_user):
    client = APIClient()
    client.force_authenticate(user=support_user)
    return client
