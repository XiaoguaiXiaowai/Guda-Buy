"""CMS 缓存：版本号批量失效，禁止 KEYS 扫描（架构文档 3.6 / 10.9）。"""

from django.core.cache import caches

from apps.catalog import cache as catalog_cache

CMS_VERSION_KEY = "cms:version"
CMS_PAGE_KEY = "cms:page:{slug}:v{version}"
CMS_PAGE_MISSING_KEY = "cms:page:missing:{slug}:v{version}"
CMS_HOME_KEY = "cms:home:v{cms_version}:p{product_version}"

MISSING_TTL_SECONDS = 60


def _cache():
    return caches["default"]


def _version(key: str) -> int:
    return int(_cache().get_or_set(key, 1, timeout=None))


def _bump(key: str) -> None:
    try:
        _cache().incr(key)
    except ValueError:
        _cache().set(key, 2, timeout=None)


def bump_cms_version() -> None:
    _bump(CMS_VERSION_KEY)


def cms_version() -> int:
    return _version(CMS_VERSION_KEY)


def page_key(slug: str) -> str:
    return CMS_PAGE_KEY.format(slug=slug, version=cms_version())


def page_missing_key(slug: str) -> str:
    return CMS_PAGE_MISSING_KEY.format(slug=slug, version=cms_version())


def home_key() -> str:
    return CMS_HOME_KEY.format(
        cms_version=cms_version(),
        product_version=catalog_cache.product_version(),
    )


def get_cache():
    return _cache()
