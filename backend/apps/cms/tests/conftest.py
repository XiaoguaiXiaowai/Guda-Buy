import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.cache import caches
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import Category, Product
from apps.cms.models import CmsAnnouncement, CmsBanner, CmsPage, CmsSection


@pytest.fixture(autouse=True)
def clear_cache():
    caches["default"].clear()
    yield
    caches["default"].clear()


@pytest.fixture
def client():
    return APIClient()


def _user(username: str, group: str | None = None) -> User:
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="Passw0rd123",
    )
    if group:
        role, _ = Group.objects.get_or_create(name=group)
        user.groups.add(role)
    return user


@pytest.fixture
def customer(db):
    return _user("cms_customer")


@pytest.fixture
def operator(db):
    return _user("cms_operator", "operator")


@pytest.fixture
def support(db):
    return _user("cms_support", "support")


@pytest.fixture
def operator_client(client, operator):
    client.force_authenticate(user=operator)
    return client


@pytest.fixture
def customer_client(client, customer):
    client.force_authenticate(user=customer)
    return client


@pytest.fixture
def section(db):
    return CmsSection.objects.create(name="帮助中心", slug="help", sort_weight=1)


@pytest.fixture
def draft_page(db, section):
    return CmsPage.objects.create(
        section=section,
        slug="shipping",
        title="配送说明",
        content="<p>48 小时内发货</p>",
    )


@pytest.fixture
def published_page(db, section):
    return CmsPage.objects.create(
        section=section,
        slug="about",
        title="关于 GUDA",
        content="<p>品牌故事</p>",
        status=CmsPage.Status.PUBLISHED,
        published_at=timezone.now(),
    )


@pytest.fixture
def banner(db):
    return CmsBanner.objects.create(
        title="春季上新",
        image="cms/banners/demo.png",
        sort_weight=10,
    )


@pytest.fixture
def announcement(db):
    return CmsAnnouncement.objects.create(
        title="系统维护通知",
        content="今晚 23:00 维护",
        level=CmsAnnouncement.Level.IMPORTANT,
        published_at=timezone.now(),
    )


@pytest.fixture
def on_sale_product(db):
    category = Category.objects.create(name="女装")
    child = Category.objects.create(name="连衣裙", parent=category)
    return Product.objects.create(
        category=child,
        name="法式碎花连衣裙",
        status=Product.Status.ON_SALE,
        price_min=Decimal("99.00"),
        price_max=Decimal("129.00"),
    )


def make_banner(**kwargs) -> CmsBanner:
    defaults = {
        "title": "轮播",
        "image": "cms/banners/demo.png",
        "status": CmsBanner.Status.ENABLED,
        "sort_weight": 0,
    }
    defaults.update(kwargs)
    return CmsBanner.objects.create(**defaults)


def window(days_before_start: int = 1, duration_days: int = 2) -> tuple:
    start = timezone.now() + timedelta(days=days_before_start)
    return start, start + timedelta(days=duration_days)


def png_upload(name="cover.png", content_type="image/png"):
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), color=(255, 255, 255)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)
