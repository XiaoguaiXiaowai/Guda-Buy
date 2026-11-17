"""T3.1 页面状态机、可见性与缓存失效（V3-1 / V3-2 / V3-4 / V3-5）。"""

import pytest

from apps.cms.models import CmsPage, CmsSection

PAGES_URL = "/api/v1/admin/cms/pages/"


def publish_url(public_id: str) -> str:
    return f"{PAGES_URL}{public_id}/publish/"


def test_draft_page_is_invisible(draft_page, client):
    response = client.get(f"/api/v1/cms/pages/{draft_page.slug}/")
    assert response.status_code == 404
    assert response.json()["code"] == "CMS_PAGE_NOT_FOUND"


def test_publish_then_offline(draft_page, operator_client):
    response = operator_client.post(publish_url(draft_page.public_id), {"action": "PUBLISH"})
    assert response.status_code == 200
    assert response.json()["status"] == "PUBLISHED"

    public = operator_client.get(f"/api/v1/cms/pages/{draft_page.slug}/")
    assert public.status_code == 200
    assert public.json()["title"] == "配送说明"
    assert "<p>48 小时内发货</p>" in public.json()["content"]

    response = operator_client.post(publish_url(draft_page.public_id), {"action": "OFFLINE"})
    assert response.status_code == 200
    assert response.json()["status"] == "OFFLINE"

    assert operator_client.get(f"/api/v1/cms/pages/{draft_page.slug}/").status_code == 404


def test_republish_from_offline_is_allowed(draft_page, operator_client):
    operator_client.post(publish_url(draft_page.public_id), {"action": "PUBLISH"})
    operator_client.post(publish_url(draft_page.public_id), {"action": "OFFLINE"})
    response = operator_client.post(publish_url(draft_page.public_id), {"action": "PUBLISH"})
    assert response.status_code == 200
    assert response.json()["status"] == "PUBLISHED"


def test_draft_cannot_be_offlined(draft_page, operator_client):
    response = operator_client.post(publish_url(draft_page.public_id), {"action": "OFFLINE"})
    assert response.status_code == 409
    assert response.json()["code"] == "CMS_STATUS_CONFLICT"


def test_publish_sanitizes_content(draft_page, operator_client):
    response = operator_client.put(
        f"{PAGES_URL}{draft_page.public_id}/",
        {
            "content": '<p>安全正文</p><script>alert("xss")</script>'
            '<img src="https://evil.example.com/a.png">'
        },
    )
    assert response.status_code == 200
    assert "script" not in response.json()["content"]
    assert "evil.example.com" not in response.json()["content"]

    operator_client.post(publish_url(draft_page.public_id), {"action": "PUBLISH"})
    public = operator_client.get(f"/api/v1/cms/pages/{draft_page.slug}/")
    assert "script" not in public.json()["content"]


def test_published_page_cache_invalidated_on_update(published_page, operator_client):
    first = operator_client.get(f"/api/v1/cms/pages/{published_page.slug}/")
    assert "品牌故事" in first.json()["content"]

    operator_client.put(
        f"{PAGES_URL}{published_page.public_id}/",
        {"content": "<p>更新后的正文</p>"},
    )
    second = operator_client.get(f"/api/v1/cms/pages/{published_page.slug}/")
    assert second.json()["content"] == "<p>更新后的正文</p>"


def test_disabled_section_hides_page(published_page, operator_client):
    section = CmsSection.objects.get(pk=published_page.section_id)
    section.status = CmsSection.Status.DISABLED
    section.save(update_fields=["status"])

    response = operator_client.get(f"/api/v1/cms/pages/{published_page.slug}/")
    assert response.status_code == 404


def test_duplicate_slug_rejected(section, operator_client):
    response = operator_client.post(
        PAGES_URL,
        {"section_public_id": section.public_id, "slug": "help-center", "title": "帮助"},
    )
    assert response.status_code == 201
    duplicate = operator_client.post(
        PAGES_URL,
        {"section_public_id": section.public_id, "slug": "help-center", "title": "重复"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "CMS_SLUG_EXISTS"


@pytest.mark.parametrize("slug", ["Bad Slug", "中文", "-leading", "trailing-"])
def test_invalid_slug_rejected(section, operator_client, slug):
    response = operator_client.post(
        PAGES_URL,
        {"section_public_id": section.public_id, "slug": slug, "title": "标题"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "COMMON_VALIDATION_ERROR"


def test_admin_page_list_supports_filters(draft_page, published_page, operator_client):
    response = operator_client.get(PAGES_URL, {"status": "DRAFT"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["slug"] == draft_page.slug

    search = operator_client.get(PAGES_URL, {"search": "GUDA"})
    assert search.json()["count"] == 1
    assert search.json()["results"][0]["slug"] == published_page.slug


def test_published_page_cannot_be_deleted(published_page, operator_client):
    response = operator_client.delete(f"{PAGES_URL}{published_page.public_id}/")
    assert response.status_code == 409
    assert response.json()["code"] == "CMS_STATUS_CONFLICT"


def test_delete_draft_page_frees_slug(draft_page, operator_client):
    response = operator_client.delete(f"{PAGES_URL}{draft_page.public_id}/")
    assert response.status_code == 204
    assert not CmsPage.objects.filter(pk=draft_page.pk, is_deleted=False).exists()

    recreate = operator_client.post(
        PAGES_URL,
        {
            "section_public_id": draft_page.section.public_id,
            "slug": draft_page.slug,
            "title": "重新创建",
        },
    )
    assert recreate.status_code == 201
