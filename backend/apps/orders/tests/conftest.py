import uuid
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, Permission
from django.core.cache import caches
from django.db.models import F
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Address, User
from apps.catalog.models import Category, Product, Sku
from apps.orders.models import Order, OrderItem, OrderStatusLog
from apps.payments.models import Payment


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
        username="order_user",
        email="order_user@example.com",
        password="Passw0rd123",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="order_other",
        email="order_other@example.com",
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


def make_address(user, *, receiver_name="张三", phone="13800138000", is_default=True):
    address = Address(
        user=user,
        receiver_name=receiver_name,
        province="浙江省",
        city="杭州市",
        district="西湖区",
        detail="文三路 100 号 1 幢 2 单元 301",
        postal_code="310012",
        is_default=is_default,
    )
    address.set_phone(phone)
    address.save()
    return address


@pytest.fixture
def address(user):
    return make_address(user)


@pytest.fixture
def other_address(other_user):
    return make_address(other_user, receiver_name="李四", phone="13900139000", is_default=False)


def make_cart_item(user, sku, quantity=1):
    from apps.cart.models import CartItem

    return CartItem.objects.create(user=user, sku=sku, quantity=quantity)


def build_order(
    user,
    address,
    sku,
    *,
    status=Order.Status.PENDING_PAYMENT,
    quantity=1,
    lock_stock=False,
    shipped_at=None,
    idempotency_key=None,
):
    """直接构造订单，供查询/发货/任务类用例使用。"""
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
        pay_expires_at=timezone.now() + timezone.timedelta(minutes=30),
        shipped_at=shipped_at,
        idempotency_key=idempotency_key,
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
        amount=order.payable_amount,
        status=Payment.Status.PENDING,
    )
    if lock_stock:
        Sku.objects.filter(pk=sku.pk).update(locked_stock=F("locked_stock") + quantity)
        sku.refresh_from_db()
    return order


@pytest.fixture
def support_user(db):
    user = User.objects.create_user(
        username="order_support",
        email="support@example.com",
        password="Passw0rd123",
        is_staff=True,
    )
    user.groups.add(Group.objects.create(name="support"))
    return user


@pytest.fixture
def operator_user(db):
    user = User.objects.create_user(
        username="order_operator",
        email="operator@example.com",
        password="Passw0rd123",
        is_staff=True,
    )
    group = Group.objects.create(name="operator")
    group.permissions.add(
        Permission.objects.get(codename="view_all_order"),
        Permission.objects.get(codename="ship_order"),
    )
    user.groups.add(group)
    return user


@pytest.fixture
def support_client(support_user):
    client = APIClient()
    client.force_authenticate(user=support_user)
    return client


@pytest.fixture
def operator_client(operator_user):
    client = APIClient()
    client.force_authenticate(user=operator_user)
    return client
