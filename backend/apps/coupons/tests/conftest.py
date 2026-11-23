"""优惠券测试公共夹具。"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.cache import caches
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import Category, Product
from apps.coupons.models import Coupon, CouponScope, UserCoupon
from apps.orders.tests.conftest import make_address, make_cart_item, make_sku


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
        username="coupon_user",
        email="coupon_user@example.com",
        password="Passw0rd123",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="coupon_other",
        email="coupon_other@example.com",
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
def operator_user(db):
    from django.contrib.auth.models import Group

    user = User.objects.create_user(
        username="coupon_operator",
        email="coupon_operator@example.com",
        password="Passw0rd123",
        is_staff=True,
    )
    user.groups.add(Group.objects.create(name="operator"))
    return user


@pytest.fixture
def operator_client(operator_user):
    client = APIClient()
    client.force_authenticate(user=operator_user)
    return client


@pytest.fixture
def category(db):
    return Category.objects.create(name="女装", sort_weight=10)


@pytest.fixture
def other_category(db):
    return Category.objects.create(name="男装", sort_weight=9)


@pytest.fixture
def product(category):
    return Product.objects.create(
        category=category,
        name="法式碎花连衣裙",
        status=Product.Status.ON_SALE,
        price_min=Decimal("120.00"),
        price_max=Decimal("120.00"),
    )


@pytest.fixture
def other_product(other_category):
    return Product.objects.create(
        category=other_category,
        name="基础款衬衫",
        status=Product.Status.ON_SALE,
        price_min=Decimal("50.00"),
        price_max=Decimal("50.00"),
    )


@pytest.fixture
def sku(product):
    return make_sku(product, sku_code="COUPON-DRESS", stock=50, sale_price="120.00")


@pytest.fixture
def other_sku(other_product):
    return make_sku(other_product, sku_code="COUPON-SHIRT", stock=50, sale_price="50.00")


@pytest.fixture
def address(user):
    return make_address(user)


@pytest.fixture
def cart_item(user, sku):
    return make_cart_item(user, sku, quantity=1)


def make_coupon(
    *,
    name="满100减20",
    coupon_type=Coupon.Type.FIXED,
    value="20.00",
    min_amount="100.00",
    total_quantity=100,
    claimed_quantity=0,
    per_user_limit=1,
    scope_type=Coupon.ScopeType.ALL,
    status=Coupon.Status.ACTIVE,
    valid_from=None,
    valid_to=None,
):
    now = timezone.now()
    return Coupon.objects.create(
        name=name,
        coupon_type=coupon_type,
        value=Decimal(value),
        min_amount=Decimal(min_amount),
        total_quantity=total_quantity,
        claimed_quantity=claimed_quantity,
        per_user_limit=per_user_limit,
        scope_type=scope_type,
        status=status,
        valid_from=valid_from or now - timedelta(days=1),
        valid_to=valid_to or now + timedelta(days=7),
    )


def make_user_coupon(user, coupon, *, status=UserCoupon.Status.UNUSED, **kwargs):
    return UserCoupon.objects.create(
        user=user,
        coupon=coupon,
        status=status,
        expires_at=kwargs.pop("expires_at", coupon.valid_to),
        **kwargs,
    )


def add_scope(coupon, *, category=None, product=None):
    return CouponScope.objects.create(coupon=coupon, category=category, product=product)
