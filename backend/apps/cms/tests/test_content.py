"""T3.3 / T3.4 轮播时间窗、公告分级与首页聚合缓存。"""

from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from apps.catalog import services as catalog_services
from apps.cms import selectors
from apps.cms.models import CmsAnnouncement, CmsBanner

from .conftest import make_banner, window

pytestmark = pytest.mark.django_db

BANNERS_URL = "/api/v1/cms/banners/"
ANNOUNCEMENTS_URL = "/api/v1/cms/announcements/"
HOME_URL = "/api/v1/cms/home/"


def test_future_banner_hidden_until_start(client):
    start, end = window(days_before_start=1)
    make_banner(start_at=start, end_at=end)

    assert client.get(BANNERS_URL).json() == []

    with freeze_time(start + timedelta(hours=1)):
        payload = client.get(BANNERS_URL).json()
    assert len(payload) == 1
    assert payload[0]["title"] == "轮播"


def test_expired_banner_hidden(client):
    start, end = window(days_before_start=-3, duration_days=1)
    make_banner(start_at=start, end_at=end)
    assert client.get(BANNERS_URL).json() == []


def test_disabled_banner_hidden(client):
    make_banner(status=CmsBanner.Status.DISABLED)
    assert client.get(BANNERS_URL).json() == []


def test_banners_ordered_by_weight(client):
    make_banner(title="低", sort_weight=1)
    make_banner(title="高", sort_weight=9)
    make_banner(title="中", sort_weight=5)
    titles = [item["title"] for item in client.get(BANNERS_URL).json()]
    assert titles == ["高", "中", "低"]


def test_banner_position_filter(client):
    make_banner(title="顶部", position=CmsBanner.Position.HOME_TOP)
    make_banner(title="中部", position=CmsBanner.Position.HOME_MIDDLE)
    payload = client.get(BANNERS_URL, {"position": "HOME_MIDDLE"}).json()
    assert [item["title"] for item in payload] == ["中部"]


def test_announcements_only_enabled_and_limited(client):
    now = timezone.now()
    CmsAnnouncement.objects.create(
        title="重要通知", level=CmsAnnouncement.Level.IMPORTANT, published_at=now
    )
    CmsAnnouncement.objects.create(title="普通通知", published_at=now - timedelta(hours=1))
    CmsAnnouncement.objects.create(
        title="已停用", status=CmsAnnouncement.Status.DISABLED, published_at=now
    )

    payload = client.get(ANNOUNCEMENTS_URL, {"limit": 1}).json()
    assert len(payload) == 1
    assert payload[0]["title"] == "重要通知"
    assert payload[0]["level"] == "IMPORTANT"


def test_home_aggregate_returns_three_blocks(client, banner, announcement, on_sale_product):
    payload = client.get(HOME_URL).json()
    assert len(payload["banners"]) == 1
    assert len(payload["announcements"]) == 1
    assert len(payload["recommended_products"]) == 1
    assert payload["recommended_products"][0]["public_id"] == on_sale_product.public_id
    assert payload["generated_at"]


def test_home_aggregate_invalidated_by_cms_write(client, operator_client):
    assert client.get(HOME_URL).json()["banners"] == []

    response = operator_client.post(
        "/api/v1/admin/cms/banners/",
        {"title": "新活动", "image": "cms/banners/a.png", "sort_weight": 1},
    )
    assert response.status_code == 201

    assert len(client.get(HOME_URL).json()["banners"]) == 1


def test_home_aggregate_invalidated_by_product_unpublish(client, on_sale_product):
    assert len(client.get(HOME_URL).json()["recommended_products"]) == 1
    catalog_services.unpublish_product(on_sale_product.public_id)
    assert client.get(HOME_URL).json()["recommended_products"] == []


def test_home_aggregate_survives_single_block_failure(client, announcement, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("banner failure")

    monkeypatch.setattr(selectors, "list_banners", boom)
    response = client.get(HOME_URL)
    assert response.status_code == 200
    payload = response.json()
    assert payload["banners"] == []
    assert len(payload["announcements"]) == 1


def test_invalid_banner_window_rejected(operator_client):
    start, _ = window(days_before_start=2)
    response = operator_client.post(
        "/api/v1/admin/cms/banners/",
        {
            "title": "倒置窗口",
            "image": "cms/banners/a.png",
            "start_at": start.isoformat(),
            "end_at": (start - timedelta(days=1)).isoformat(),
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "COMMON_VALIDATION_ERROR"
