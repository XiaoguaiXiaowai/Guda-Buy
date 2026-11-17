"""商品缓存：版本号批量失效，禁止 KEYS 扫描（架构文档 3.6）。"""

from django.core.cache import caches

CATEGORY_TREE_VERSION_KEY = "catalog:category:tree:version"
PRODUCT_VERSION_KEY = "catalog:product:version"
CATEGORY_TREE_KEY = "catalog:category:tree:v{version}"
PRODUCT_DETAIL_KEY = "catalog:product:{public_id}:v{version}"
PRODUCT_MISSING_KEY = "catalog:product:missing:{public_id}:v{version}"
PRODUCT_DETAIL_LOCK_KEY = "catalog:product:lock:{public_id}"

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


def bump_category_version() -> None:
    _bump(CATEGORY_TREE_VERSION_KEY)


def bump_product_version() -> None:
    _bump(PRODUCT_VERSION_KEY)


def product_version() -> int:
    """供首页聚合等跨模块缓存 key 组合使用。"""
    return _version(PRODUCT_VERSION_KEY)


def category_tree_key() -> str:
    return CATEGORY_TREE_KEY.format(version=_version(CATEGORY_TREE_VERSION_KEY))


def product_detail_key(public_id: str) -> str:
    return PRODUCT_DETAIL_KEY.format(public_id=public_id, version=_version(PRODUCT_VERSION_KEY))


def product_missing_key(public_id: str) -> str:
    return PRODUCT_MISSING_KEY.format(public_id=public_id, version=_version(PRODUCT_VERSION_KEY))


def get_cache():
    return _cache()
