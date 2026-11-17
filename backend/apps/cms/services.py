"""CMS 领域服务：栏目、页面、轮播与公告的唯一写入口（架构文档 10.9）。"""

import logging
import secrets

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from apps.cms import cache
from apps.cms.models import CmsAnnouncement, CmsBanner, CmsPage, CmsSection
from apps.cms.sanitizer import SLUG_PATTERN, sanitize_html
from apps.common.exceptions import BusinessError

logger = logging.getLogger("guda.cms")

IMAGE_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
IMAGE_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
IMAGE_MAX_BYTES = 5 * 1024 * 1024
IMAGE_MAX_SIDE = 4096

PAGE_TRANSITIONS = {
    CmsPage.Status.DRAFT: {CmsPage.Status.PUBLISHED},
    CmsPage.Status.PUBLISHED: {CmsPage.Status.OFFLINE},
    CmsPage.Status.OFFLINE: {CmsPage.Status.PUBLISHED},
}


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------
def _invalidate() -> None:
    cache.bump_cms_version()


def _audit(action: str, target, operator, detail: str = "") -> None:
    """后台操作审计：结构化日志记录操作人、对象与动作。"""
    logger.info(
        "cms audit action=%s target=%s operator=%s detail=%s",
        action,
        getattr(target, "public_id", "-"),
        getattr(operator, "public_id", None),
        detail,
        extra={"action": action, "result": "ok"},
    )


def _clean_slug(slug: str) -> str:
    slug = (slug or "").strip().lower()
    if not SLUG_PATTERN.match(slug):
        raise BusinessError(
            "COMMON_VALIDATION_ERROR",
            "slug 需为 1–64 位小写字母、数字或连字符，且不能以连字符开头或结尾",
        )
    return slug


def _clean_content(content: str) -> str:
    raw = content or ""
    if len(raw) > settings.CMS_CONTENT_MAX_LENGTH:
        raise BusinessError(
            "COMMON_VALIDATION_ERROR",
            f"正文不能超过 {settings.CMS_CONTENT_MAX_LENGTH} 个字符",
        )
    return sanitize_html(raw)


def _clean_link(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    lowered = value.lower()
    if lowered.startswith(("javascript:", "data:", "vbscript:")):
        raise BusinessError("COMMON_VALIDATION_ERROR", "跳转链接协议不合法")
    if value.startswith(("/", "#")) or lowered.startswith(("http://", "https://", "mailto:")):
        return value
    raise BusinessError("COMMON_VALIDATION_ERROR", "跳转链接需为站内路径或 http(s) 地址")


def _validate_window(start_at, end_at) -> None:
    if start_at and end_at and start_at >= end_at:
        raise BusinessError("COMMON_VALIDATION_ERROR", "开始时间必须早于结束时间")


def _unique_slug(model, slug: str, exclude_pk: int | None = None) -> str:
    exists = model.objects.filter(slug=slug)
    if exclude_pk is not None:
        exists = exists.exclude(pk=exclude_pk)
    if exists.exists():
        raise BusinessError("CMS_SLUG_EXISTS", "slug 已被占用", http_status=409)
    return slug


def _validate_image_file(uploaded_file) -> tuple[str, str]:
    filename = uploaded_file.name or ""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in IMAGE_ALLOWED_EXTENSIONS:
        raise BusinessError("COMMON_VALIDATION_ERROR", "仅支持 jpg/jpeg/png/webp 格式图片")
    if (uploaded_file.content_type or "") not in IMAGE_ALLOWED_CONTENT_TYPES:
        raise BusinessError("COMMON_VALIDATION_ERROR", "图片 MIME 类型不合法")
    if uploaded_file.size > IMAGE_MAX_BYTES:
        raise BusinessError("COMMON_VALIDATION_ERROR", "图片不能超过 5MB")

    try:
        image = Image.open(uploaded_file)
        image.verify()
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        width, height = image.size
        uploaded_file.seek(0)
    except (UnidentifiedImageError, OSError) as exc:
        raise BusinessError("COMMON_VALIDATION_ERROR", "图片文件已损坏或格式不正确") from exc

    if width > IMAGE_MAX_SIDE or height > IMAGE_MAX_SIDE:
        raise BusinessError("COMMON_VALIDATION_ERROR", "图片尺寸不能超过 4096px")
    return ("jpg" if extension == "jpeg" else extension), uploaded_file.read()


# ---------------------------------------------------------------------------
# 栏目
# ---------------------------------------------------------------------------
def get_section(public_id: str) -> CmsSection:
    section = CmsSection.objects.filter(public_id=public_id, is_deleted=False).first()
    if section is None:
        raise BusinessError("CMS_SECTION_NOT_FOUND", "栏目不存在", http_status=404)
    return section


def create_section(data: dict, operator=None) -> CmsSection:
    slug = _unique_slug(CmsSection, _clean_slug(data["slug"]))
    section = CmsSection.objects.create(
        name=data["name"].strip(),
        slug=slug,
        sort_weight=data.get("sort_weight", 0),
        status=data.get("status", CmsSection.Status.ENABLED),
    )
    _invalidate()
    _audit("cms.create_section", section, operator)
    return section


def update_section(public_id: str, data: dict, operator=None) -> CmsSection:
    section = get_section(public_id)
    payload = dict(data)
    if "slug" in payload:
        section.slug = _unique_slug(
            CmsSection, _clean_slug(payload.pop("slug")), exclude_pk=section.pk
        )
    if "name" in payload:
        section.name = payload.pop("name").strip()
    for key, value in payload.items():
        setattr(section, key, value)
    section.save()
    _invalidate()
    _audit("cms.update_section", section, operator)
    return section


def delete_section(public_id: str, operator=None) -> None:
    section = get_section(public_id)
    if section.pages.filter(is_deleted=False).exists():
        raise BusinessError("CMS_SECTION_NOT_EMPTY", "栏目下存在页面，无法删除", http_status=409)
    section.soft_delete()
    _invalidate()
    _audit("cms.delete_section", section, operator)


# ---------------------------------------------------------------------------
# 页面
# ---------------------------------------------------------------------------
def get_page(public_id: str) -> CmsPage:
    page = CmsPage.objects.filter(public_id=public_id, is_deleted=False).first()
    if page is None:
        raise BusinessError("CMS_PAGE_NOT_FOUND", "页面不存在", http_status=404)
    return page


def create_page(data: dict, operator=None) -> CmsPage:
    payload = dict(data)
    section = get_section(payload.pop("section_public_id"))
    slug = _unique_slug(CmsPage, _clean_slug(payload.pop("slug")))
    page = CmsPage.objects.create(
        section=section,
        slug=slug,
        title=payload.pop("title").strip(),
        content=_clean_content(payload.pop("content", "")),
        seo_title=payload.pop("seo_title", "").strip(),
        seo_description=payload.pop("seo_description", "").strip(),
        sort_weight=payload.pop("sort_weight", 0),
        status=CmsPage.Status.DRAFT,
        created_by=operator,
        updated_by=operator,
        **payload,
    )
    _invalidate()
    _audit("cms.create_page", page, operator)
    return page


def update_page(public_id: str, data: dict, operator=None) -> CmsPage:
    page = get_page(public_id)
    payload = dict(data)
    if "section_public_id" in payload:
        page.section = get_section(payload.pop("section_public_id"))
    if "slug" in payload:
        page.slug = _unique_slug(CmsPage, _clean_slug(payload.pop("slug")), exclude_pk=page.pk)
    if "content" in payload:
        page.content = _clean_content(payload.pop("content"))
    for key in ("title", "seo_title", "seo_description"):
        if key in payload:
            setattr(page, key, payload.pop(key).strip())
    for key, value in payload.items():
        setattr(page, key, value)
    page.updated_by = operator
    page.save()
    _invalidate()
    _audit("cms.change_page", page, operator)
    return page


def change_page_status(public_id: str, action: str, operator=None) -> CmsPage:
    """发布 / 下线：只允许 DRAFT→PUBLISHED→OFFLINE 与 OFFLINE→PUBLISHED。"""
    page = get_page(public_id)
    target = {
        "PUBLISH": CmsPage.Status.PUBLISHED,
        "OFFLINE": CmsPage.Status.OFFLINE,
    }.get((action or "").upper())
    if target is None:
        raise BusinessError("COMMON_VALIDATION_ERROR", "action 仅支持 PUBLISH 或 OFFLINE")

    if page.status == target:
        return page
    if target not in PAGE_TRANSITIONS.get(page.status, set()):
        raise BusinessError(
            "CMS_STATUS_CONFLICT",
            f"页面状态不允许从 {page.status} 变更为 {target}",
            http_status=409,
        )

    with transaction.atomic():
        page.status = target
        page.published_at = timezone.now() if target == CmsPage.Status.PUBLISHED else None
        page.updated_by = operator
        page.save(update_fields=["status", "published_at", "updated_by", "updated_at"])
    _invalidate()
    _audit(
        "cms.publish_page" if target == CmsPage.Status.PUBLISHED else "cms.offline_page",
        page,
        operator,
    )
    return page


def delete_page(public_id: str, operator=None) -> None:
    page = get_page(public_id)
    if page.status == CmsPage.Status.PUBLISHED:
        raise BusinessError("CMS_STATUS_CONFLICT", "已发布页面请先下线再删除", http_status=409)
    deleted_slug = f"{page.slug[:48]}-del-{page.public_id[:6]}"
    page.slug = deleted_slug
    page.save(update_fields=["slug", "updated_at"])
    page.soft_delete()
    _invalidate()
    _audit("cms.delete_page", page, operator)


# ---------------------------------------------------------------------------
# 轮播位
# ---------------------------------------------------------------------------
def get_banner(public_id: str) -> CmsBanner:
    banner = CmsBanner.objects.filter(public_id=public_id, is_deleted=False).first()
    if banner is None:
        raise BusinessError("CMS_BANNER_NOT_FOUND", "轮播位不存在", http_status=404)
    return banner


def create_banner(data: dict, operator=None) -> CmsBanner:
    payload = dict(data)
    _validate_window(payload.get("start_at"), payload.get("end_at"))
    payload["link_url"] = _clean_link(payload.get("link_url", ""))
    banner = CmsBanner.objects.create(created_by=operator, updated_by=operator, **payload)
    _invalidate()
    _audit("cms.create_banner", banner, operator)
    return banner


def update_banner(public_id: str, data: dict, operator=None) -> CmsBanner:
    banner = get_banner(public_id)
    payload = dict(data)
    if "link_url" in payload:
        payload["link_url"] = _clean_link(payload["link_url"])
    _validate_window(payload.get("start_at", banner.start_at), payload.get("end_at", banner.end_at))
    for key, value in payload.items():
        setattr(banner, key, value)
    banner.updated_by = operator
    banner.save()
    _invalidate()
    _audit("cms.change_banner", banner, operator)
    return banner


def delete_banner(public_id: str, operator=None) -> None:
    banner = get_banner(public_id)
    image = banner.image
    banner.soft_delete()
    if image:
        default_storage.delete(image)
    _invalidate()
    _audit("cms.delete_banner", banner, operator)


def save_banner_image(public_id: str, uploaded_file, operator=None) -> CmsBanner:
    banner = get_banner(public_id)
    suffix, content = _validate_image_file(uploaded_file)
    relative_path = f"cms/banners/{banner.public_id}/{secrets.token_hex(8)}.{suffix}"
    saved_path = default_storage.save(relative_path, ContentFile(content))

    previous = banner.image
    banner.image = saved_path
    banner.updated_by = operator
    banner.save(update_fields=["image", "updated_by", "updated_at"])
    if previous and previous != saved_path:
        default_storage.delete(previous)
    _invalidate()
    _audit("cms.upload_banner_image", banner, operator)
    return banner


# ---------------------------------------------------------------------------
# 公告
# ---------------------------------------------------------------------------
def get_announcement(public_id: str) -> CmsAnnouncement:
    announcement = CmsAnnouncement.objects.filter(public_id=public_id, is_deleted=False).first()
    if announcement is None:
        raise BusinessError("CMS_ANNOUNCEMENT_NOT_FOUND", "公告不存在", http_status=404)
    return announcement


def _announcement_publish_time(status: str, published_at):
    if status == CmsAnnouncement.Status.ENABLED and published_at is None:
        return timezone.now()
    return published_at


def create_announcement(data: dict, operator=None) -> CmsAnnouncement:
    payload = dict(data)
    content = payload.pop("content", "") or ""
    if len(content) > 2000:
        raise BusinessError("COMMON_VALIDATION_ERROR", "公告正文不能超过 2000 个字符")
    payload["content"] = content
    payload["published_at"] = _announcement_publish_time(
        payload.get("status", CmsAnnouncement.Status.ENABLED), payload.get("published_at")
    )
    announcement = CmsAnnouncement.objects.create(**payload)
    _invalidate()
    _audit("cms.create_announcement", announcement, operator)
    return announcement


def update_announcement(public_id: str, data: dict, operator=None) -> CmsAnnouncement:
    announcement = get_announcement(public_id)
    payload = dict(data)
    if "content" in payload:
        content = payload["content"] or ""
        if len(content) > 2000:
            raise BusinessError("COMMON_VALIDATION_ERROR", "公告正文不能超过 2000 个字符")
        payload["content"] = content
    status = payload.get("status", announcement.status)
    payload["published_at"] = _announcement_publish_time(
        status, payload.get("published_at", announcement.published_at)
    )
    for key, value in payload.items():
        setattr(announcement, key, value)
    announcement.save()
    _invalidate()
    _audit("cms.change_announcement", announcement, operator)
    return announcement


def delete_announcement(public_id: str, operator=None) -> None:
    announcement = get_announcement(public_id)
    announcement.soft_delete()
    _invalidate()
    _audit("cms.delete_announcement", announcement, operator)
