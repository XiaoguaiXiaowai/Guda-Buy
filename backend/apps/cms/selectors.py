"""CMS 只读查询：前台页面/轮播/公告、首页聚合与后台列表。"""

import logging

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from apps.catalog import selectors as catalog_selectors
from apps.catalog.models import Product
from apps.cms import cache
from apps.cms.models import CmsAnnouncement, CmsBanner, CmsPage, CmsSection
from apps.common.exceptions import BusinessError

logger = logging.getLogger("guda.cms")


# ---------------------------------------------------------------------------
# 前台
# ---------------------------------------------------------------------------
def _page_payload(page: CmsPage) -> dict:
    return {
        "public_id": page.public_id,
        "slug": page.slug,
        "title": page.title,
        "content": page.content,
        "seo_title": page.seo_title,
        "seo_description": page.seo_description,
        "section": {
            "public_id": page.section.public_id,
            "name": page.section.name,
            "slug": page.section.slug,
        },
        "published_at": page.published_at.isoformat() if page.published_at else None,
        "updated_at": page.updated_at.isoformat(),
    }


def get_page(slug: str) -> dict:
    """仅 PUBLISHED 且栏目启用的页面对外可见；空值缓存 60 秒防击穿。"""
    slug = (slug or "").strip().lower()
    if not slug:
        raise BusinessError("CMS_PAGE_NOT_FOUND", "页面不存在或未发布", http_status=404)

    key = cache.page_key(slug)
    cached = cache.get_cache().get(key)
    if cached is not None:
        return cached
    if cache.get_cache().get(cache.page_missing_key(slug)) is not None:
        raise BusinessError("CMS_PAGE_NOT_FOUND", "页面不存在或未发布", http_status=404)

    page = (
        CmsPage.objects.filter(
            slug=slug,
            status=CmsPage.Status.PUBLISHED,
            is_deleted=False,
            section__is_deleted=False,
            section__status=CmsSection.Status.ENABLED,
        )
        .select_related("section")
        .first()
    )
    if page is None:
        cache.get_cache().set(cache.page_missing_key(slug), 1, timeout=cache.MISSING_TTL_SECONDS)
        raise BusinessError("CMS_PAGE_NOT_FOUND", "页面不存在或未发布", http_status=404)

    payload = _page_payload(page)
    cache.get_cache().set(key, payload, timeout=settings.CMS_PAGE_CACHE_SECONDS)
    return payload


def _banner_payload(banner: CmsBanner) -> dict:
    return {
        "public_id": banner.public_id,
        "position": banner.position,
        "title": banner.title,
        "image": banner.image,
        "link_url": banner.link_url,
        "sort_weight": banner.sort_weight,
    }


def list_banners(position: str | None = None) -> list[dict]:
    now = timezone.now()
    queryset = (
        CmsBanner.objects.filter(
            is_deleted=False,
            status=CmsBanner.Status.ENABLED,
        )
        .filter(Q(start_at__isnull=True) | Q(start_at__lte=now))
        .filter(Q(end_at__isnull=True) | Q(end_at__gte=now))
    )
    if position:
        queryset = queryset.filter(position=position)
    return [_banner_payload(banner) for banner in queryset.order_by("-sort_weight", "id")]


def _announcement_payload(announcement: CmsAnnouncement) -> dict:
    return {
        "public_id": announcement.public_id,
        "title": announcement.title,
        "content": announcement.content,
        "level": announcement.level,
        "published_at": (
            announcement.published_at.isoformat() if announcement.published_at else None
        ),
    }


def list_announcements(limit: int | None = None) -> list[dict]:
    now = timezone.now()
    queryset = CmsAnnouncement.objects.filter(
        is_deleted=False,
        status=CmsAnnouncement.Status.ENABLED,
    ).filter(Q(published_at__isnull=True) | Q(published_at__lte=now))
    queryset = queryset.order_by("-published_at", "-id")
    if limit:
        queryset = queryset[:limit]
    return [_announcement_payload(item) for item in queryset]


def _recommended_products() -> list[dict]:
    products = (
        Product.objects.filter(
            is_deleted=False,
            status=Product.Status.ON_SALE,
            category__is_deleted=False,
        )
        .select_related("category")
        .order_by("-sales_count", "-sort_weight", "-id")[: settings.CMS_HOME_RECOMMEND_LIMIT]
    )
    return [catalog_selectors.product_list_item(product) for product in products]


def home_aggregate() -> dict:
    """首页聚合：轮播 + 公告 + 推荐商品；任一区块失败不影响其他区块。"""
    key = cache.home_key()
    cached = cache.get_cache().get(key)
    if cached is not None:
        logger.info("cms home cache hit", extra={"action": "cms.home_cache_hit", "result": "ok"})
        return cached

    logger.info("cms home cache miss", extra={"action": "cms.home_cache_miss", "result": "ok"})
    payload: dict = {"banners": [], "announcements": [], "recommended_products": []}

    try:
        payload["banners"] = list_banners(CmsBanner.Position.HOME_TOP)
    except Exception:  # noqa: BLE001 - 单区块失败不拖垮首页
        logger.exception("首页轮播加载失败", extra={"action": "cms.home_banners_failed"})
    try:
        payload["announcements"] = list_announcements(limit=3)
    except Exception:  # noqa: BLE001
        logger.exception("首页公告加载失败", extra={"action": "cms.home_announcements_failed"})
    try:
        payload["recommended_products"] = _recommended_products()
    except Exception:  # noqa: BLE001
        logger.exception("首页推荐加载失败", extra={"action": "cms.home_recommend_failed"})

    payload["generated_at"] = timezone.now().isoformat()
    cache.get_cache().set(key, payload, timeout=settings.CMS_HOME_CACHE_SECONDS)
    return payload


# ---------------------------------------------------------------------------
# 后台
# ---------------------------------------------------------------------------
def admin_section_queryset():
    return (
        CmsSection.objects.filter(is_deleted=False)
        .annotate(page_count=Count("pages", filter=Q(pages__is_deleted=False)))
        .order_by("sort_weight", "id")
    )


def get_admin_section(public_id: str) -> CmsSection:
    section = admin_section_queryset().filter(public_id=public_id).first()
    if section is None:
        raise BusinessError("CMS_SECTION_NOT_FOUND", "栏目不存在", http_status=404)
    return section


def admin_page_queryset(params):
    queryset = (
        CmsPage.objects.filter(is_deleted=False)
        .select_related("section")
        .order_by("sort_weight", "-updated_at", "-id")
    )
    status = (params.get("status") or "").strip()
    if status:
        queryset = queryset.filter(status=status)
    section_public_id = (params.get("section") or "").strip()
    if section_public_id:
        queryset = queryset.filter(section__public_id=section_public_id)
    search = (params.get("search") or "").strip()[:30]
    if search:
        queryset = queryset.filter(Q(title__icontains=search) | Q(slug__icontains=search))
    return queryset


def get_admin_page(public_id: str) -> CmsPage:
    page = (
        CmsPage.objects.filter(public_id=public_id, is_deleted=False)
        .select_related("section")
        .first()
    )
    if page is None:
        raise BusinessError("CMS_PAGE_NOT_FOUND", "页面不存在", http_status=404)
    return page


def admin_banner_queryset(params):
    queryset = CmsBanner.objects.filter(is_deleted=False).order_by("-sort_weight", "id")
    position = (params.get("position") or "").strip()
    if position:
        queryset = queryset.filter(position=position)
    status = (params.get("status") or "").strip()
    if status:
        queryset = queryset.filter(status=status)
    return queryset


def admin_announcement_queryset(params):
    queryset = CmsAnnouncement.objects.filter(is_deleted=False).order_by("-published_at", "-id")
    status = (params.get("status") or "").strip()
    if status:
        queryset = queryset.filter(status=status)
    level = (params.get("level") or "").strip()
    if level:
        queryset = queryset.filter(level=level)
    return queryset
