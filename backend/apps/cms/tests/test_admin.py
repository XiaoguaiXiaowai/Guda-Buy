"""T3.5 后台权限、CRUD 与图片上传（V3-6）。"""

import logging

from django.contrib.auth.models import Permission

from apps.cms.models import CmsAnnouncement, CmsBanner, CmsPage

from .conftest import png_upload

SECTIONS_URL = "/api/v1/admin/cms/sections/"
PAGES_URL = "/api/v1/admin/cms/pages/"
BANNERS_URL = "/api/v1/admin/cms/banners/"
ANNOUNCEMENTS_URL = "/api/v1/admin/cms/announcements/"


def test_cms_permission_points_exist(db):
    codenames = set(
        Permission.objects.filter(content_type__app_label="cms").values_list("codename", flat=True)
    )
    assert {"change_page", "publish_page"} <= codenames


def test_anonymous_cannot_access_admin(client):
    response = client.get(SECTIONS_URL)
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_TOKEN_INVALID"


def test_customer_cannot_access_admin(customer_client):
    assert customer_client.get(SECTIONS_URL).status_code == 403
    assert customer_client.post(SECTIONS_URL, {"name": "x", "slug": "x"}).status_code == 403


def test_support_cannot_publish_page(support, client, draft_page):
    client.force_authenticate(user=support)
    response = client.post(f"{PAGES_URL}{draft_page.public_id}/publish/", {"action": "PUBLISH"})
    assert response.status_code == 403
    assert response.json()["code"] == "COMMON_PERMISSION_DENIED"


def test_operator_manages_section_and_page(operator_client):
    created = operator_client.post(
        SECTIONS_URL, {"name": "活动专区", "slug": "campaign", "sort_weight": 2}
    )
    assert created.status_code == 201
    section_id = created.json()["public_id"]

    updated = operator_client.put(
        f"{SECTIONS_URL}{section_id}/", {"name": "活动中心", "sort_weight": 3}
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "活动中心"

    page = operator_client.post(
        PAGES_URL,
        {
            "section_public_id": section_id,
            "slug": "spring-sale",
            "title": "春季大促",
            "content": "<p>全场 8 折</p>",
            "seo_description": "春季活动",
        },
    )
    assert page.status_code == 201
    page_id = page.json()["public_id"]
    assert page.json()["status"] == "DRAFT"

    published = operator_client.post(f"{PAGES_URL}{page_id}/publish/", {"action": "PUBLISH"})
    assert published.status_code == 200
    assert published.json()["published_at"] is not None

    listing = operator_client.get(PAGES_URL, {"section": section_id})
    assert listing.json()["count"] == 1

    blocked = operator_client.delete(f"{SECTIONS_URL}{section_id}/")
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "CMS_SECTION_NOT_EMPTY"

    operator_client.post(f"{PAGES_URL}{page_id}/publish/", {"action": "OFFLINE"})
    assert operator_client.delete(f"{PAGES_URL}{page_id}/").status_code == 204
    assert operator_client.delete(f"{SECTIONS_URL}{section_id}/").status_code == 204


def test_banner_crud_and_image_upload(operator_client):
    created = operator_client.post(
        BANNERS_URL,
        {
            "title": "首页大图",
            "image": "cms/banners/placeholder.png",
            "link_url": "/page/spring-sale",
            "sort_weight": 5,
        },
    )
    assert created.status_code == 201
    banner_id = created.json()["public_id"]

    uploaded = operator_client.post(
        f"{BANNERS_URL}{banner_id}/image/", {"file": png_upload()}, format="multipart"
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["image"].startswith("cms/banners/")

    invalid = operator_client.post(
        f"{BANNERS_URL}{banner_id}/image/",
        {"file": png_upload(name="cover.png", content_type="image/gif")},
        format="multipart",
    )
    assert invalid.status_code == 400

    disabled = operator_client.put(f"{BANNERS_URL}{banner_id}/", {"status": "DISABLED"})
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "DISABLED"

    assert operator_client.delete(f"{BANNERS_URL}{banner_id}/").status_code == 204
    assert not CmsBanner.objects.filter(public_id=banner_id, is_deleted=False).exists()


def test_banner_rejects_javascript_link(operator_client):
    response = operator_client.post(
        BANNERS_URL,
        {"title": "恶意链接", "image": "cms/banners/a.png", "link_url": "javascript:alert(1)"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "COMMON_VALIDATION_ERROR"


def test_announcement_crud_sets_publish_time(operator_client):
    created = operator_client.post(
        ANNOUNCEMENTS_URL,
        {"title": "上新公告", "content": "秋季新品已上架", "level": "IMPORTANT"},
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["published_at"] is not None
    announcement_id = payload["public_id"]

    updated = operator_client.put(
        f"{ANNOUNCEMENTS_URL}{announcement_id}/", {"title": "上新公告（修订）"}
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "上新公告（修订）"

    listing = operator_client.get(ANNOUNCEMENTS_URL, {"level": "IMPORTANT"})
    assert len(listing.json()) == 1

    assert operator_client.delete(f"{ANNOUNCEMENTS_URL}{announcement_id}/").status_code == 204
    assert not CmsAnnouncement.objects.filter(public_id=announcement_id, is_deleted=False).exists()


def test_publish_writes_audit_log(draft_page, operator, operator_client, caplog):
    with caplog.at_level(logging.INFO, logger="guda.cms"):
        operator_client.post(f"{PAGES_URL}{draft_page.public_id}/publish/", {"action": "PUBLISH"})

    messages = [record.getMessage() for record in caplog.records if record.name == "guda.cms"]
    assert any(
        "action=cms.publish_page" in message and f"operator={operator.public_id}" in message
        for message in messages
    )


def test_admin_page_cache_does_not_leak_drafts(operator_client, draft_page, client):
    operator_client.post(f"{PAGES_URL}{draft_page.public_id}/publish/", {"action": "PUBLISH"})
    assert client.get(f"/api/v1/cms/pages/{draft_page.slug}/").status_code == 200
    operator_client.post(f"{PAGES_URL}{draft_page.public_id}/publish/", {"action": "OFFLINE"})
    assert client.get(f"/api/v1/cms/pages/{draft_page.slug}/").status_code == 404
    assert CmsPage.objects.filter(public_id=draft_page.public_id).exists()
