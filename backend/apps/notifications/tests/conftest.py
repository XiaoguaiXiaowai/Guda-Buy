"""站内消息测试夹具：用户、客户端、商品与消息构造。"""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import Category, Product
from apps.notifications.models import Notification
from apps.orders.tests.conftest import make_address, make_sku


@pytest.fixture(autouse=True)
def payment_settings(settings):
    settings.PAYMENT_CALLBACK_SECRET = "test-pay-secret"
    return settings


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="notify_user",
        email="notify_user@example.com",
        password="Passw0rd123",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="notify_other",
        email="notify_other@example.com",
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


def make_notification(
    user,
    *,
    notification_type=Notification.Type.SYSTEM,
    title="系统通知",
    content="系统维护通知",
    biz_type="",
    biz_public_id="",
    is_read=False,
):
    return Notification.objects.create(
        user=user,
        type=notification_type,
        title=title,
        content=content,
        biz_type=biz_type,
        biz_public_id=biz_public_id,
        is_read=is_read,
    )


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
    return make_sku(product)


@pytest.fixture
def address(user):
    return make_address(user)
