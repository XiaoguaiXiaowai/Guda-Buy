"""商品只读查询：分类树、列表、详情（缓存）、联想、相关推荐与后台列表。"""

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db.models import Case, Count, IntegerField, Prefetch, Q, QuerySet, Sum, Value, When
from django.db.models.functions import Coalesce

from apps.catalog import cache
from apps.catalog.models import Category, Product, Sku
from apps.common.exceptions import BusinessError
from apps.reviews import selectors as review_selectors

PRODUCT_ORDERING = {
    "default": ("-sort_weight", "-sales_count", "-id"),
    "price": ("price_min", "id"),
    "-price": ("-price_min", "-id"),
    "sales": ("-sales_count", "-id"),
    "-sales": ("sales_count", "id"),
    "created_at": ("created_at", "id"),
    "-created_at": ("-created_at", "-id"),
}
MAX_SEARCH_LENGTH = 30


def _money(value) -> str:
    return f"{Decimal(value or 0):.2f}"


def _on_sale_products():
    return Product.objects.filter(
        is_deleted=False,
        status=Product.Status.ON_SALE,
        category__is_deleted=False,
    )


# ---------------------------------------------------------------------------
# 分类树
# ---------------------------------------------------------------------------
def category_tree() -> list[dict]:
    key = cache.category_tree_key()
    cached = cache.get_cache().get(key)
    if cached is not None:
        return cached

    on_sale = Q(products__status=Product.Status.ON_SALE, products__is_deleted=False)
    children = (
        Category.objects.filter(is_deleted=False)
        .order_by("sort_weight", "id")
        .annotate(product_count=Count("products", filter=on_sale))
    )
    parents = (
        Category.objects.filter(parent__isnull=True, is_deleted=False)
        .order_by("sort_weight", "id")
        .prefetch_related(Prefetch("children", queryset=children))
    )

    payload = []
    for parent in parents:
        child_items = [
            {
                "public_id": child.public_id,
                "name": child.name,
                "sort_weight": child.sort_weight,
                "product_count": child.product_count,
                "children": [],
            }
            for child in parent.children.all()
            if not child.is_deleted
        ]
        payload.append(
            {
                "public_id": parent.public_id,
                "name": parent.name,
                "sort_weight": parent.sort_weight,
                "product_count": sum(item["product_count"] for item in child_items),
                "children": child_items,
            }
        )

    cache.get_cache().set(key, payload, timeout=settings.CATALOG_CATEGORY_CACHE_SECONDS)
    return payload


# ---------------------------------------------------------------------------
# 前台列表 / 详情 / 联想 / 推荐
# ---------------------------------------------------------------------------
def _parse_decimal(value: str, field: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise BusinessError("COMMON_VALIDATION_ERROR", f"{field} 需为数字") from exc


def _category_ids(public_id: str) -> list[int]:
    category = Category.objects.filter(public_id=public_id, is_deleted=False).first()
    if category is None:
        raise BusinessError("PRODUCT_CATEGORY_NOT_FOUND", "分类不存在", http_status=404)
    if category.parent_id is None:
        ids = [category.id]
        ids.extend(category.children.filter(is_deleted=False).values_list("id", flat=True))
        return ids
    return [category.id]


def _resolve_ordering(raw: str) -> tuple[str, ...]:
    if not raw:
        return PRODUCT_ORDERING["default"]
    fields: list[str] = []
    for token in raw.split(","):
        token = token.strip()
        if token in PRODUCT_ORDERING and token != "default":
            fields.extend(PRODUCT_ORDERING[token])
    return tuple(dict.fromkeys(fields)) or PRODUCT_ORDERING["default"]


def list_products(params) -> QuerySet:
    queryset = _on_sale_products().select_related("category")

    category_public_id = (params.get("category") or "").strip()
    if category_public_id:
        queryset = queryset.filter(category_id__in=_category_ids(category_public_id))

    price_min = params.get("price_min")
    if price_min not in (None, ""):
        queryset = queryset.filter(price_min__gte=_parse_decimal(price_min, "price_min"))
    price_max = params.get("price_max")
    if price_max not in (None, ""):
        queryset = queryset.filter(price_max__lte=_parse_decimal(price_max, "price_max"))

    search = (params.get("search") or "").strip()[:MAX_SEARCH_LENGTH]
    if search:
        queryset = queryset.filter(name__icontains=search)

    return queryset.order_by(*_resolve_ordering(params.get("ordering") or ""))


def _sku_payload(sku: Sku) -> dict:
    return {
        "public_id": sku.public_id,
        "sku_code": sku.sku_code,
        "spec_text": sku.spec_text,
        "specs": sku.specs,
        "sale_price": _money(sku.sale_price),
        "original_price": _money(sku.original_price) if sku.original_price is not None else None,
        "stock": sku.stock,
        "stock_status": sku.stock_status,
        "stock_text": sku.stock_text,
        "status": sku.status,
    }


def _product_detail_payload(product: Product) -> dict:
    skus = [sku for sku in product.skus.all() if sku.status == Sku.Status.ON_SALE]
    return {
        "public_id": product.public_id,
        "name": product.name,
        "subtitle": product.subtitle,
        "description": product.description,
        "main_image": product.main_image,
        "price_min": _money(product.price_min),
        "price_max": _money(product.price_max),
        "sales_count": product.sales_count,
        "category": {
            "public_id": product.category.public_id,
            "name": product.category.name,
            "parent_public_id": product.category.parent.public_id
            if product.category.parent_id
            else None,
        },
        "images": [
            {"public_id": image.public_id, "image": image.image, "sort_order": image.sort_order}
            for image in product.images.all()
        ],
        "skus": [_sku_payload(sku) for sku in skus],
        "review_summary": review_selectors.review_summary(product.id),
        "created_at": product.created_at.isoformat(),
    }


def get_product_detail(public_id: str) -> dict | None:
    key = cache.product_detail_key(public_id)
    cached = cache.get_cache().get(key)
    if cached is not None:
        return cached
    if cache.get_cache().get(cache.product_missing_key(public_id)) is not None:
        return None

    lock_key = cache.PRODUCT_DETAIL_LOCK_KEY.format(public_id=public_id)
    has_lock = cache.get_cache().add(lock_key, 1, timeout=10)
    try:
        product = (
            _on_sale_products()
            .select_related("category__parent")
            .prefetch_related("images", "skus")
            .filter(public_id=public_id)
            .first()
        )
        if product is None:
            cache.get_cache().set(
                cache.product_missing_key(public_id), 1, timeout=cache.MISSING_TTL_SECONDS
            )
            return None

        payload = _product_detail_payload(product)
        cache.get_cache().set(key, payload, timeout=settings.CATALOG_PRODUCT_CACHE_SECONDS)
        return payload
    finally:
        if has_lock:
            cache.get_cache().delete(lock_key)


def list_related(product_public_id: str, limit: int = 8) -> list[dict]:
    product = (
        _on_sale_products().select_related("category").filter(public_id=product_public_id).first()
    )
    if product is None:
        raise BusinessError("PRODUCT_NOT_FOUND", "商品不存在", http_status=404)
    related = (
        _on_sale_products()
        .select_related("category")
        .filter(category_id=product.category_id)
        .exclude(pk=product.pk)
        .order_by("-sales_count", "-sort_weight", "-id")[:limit]
    )
    return [product_list_item(item) for item in related]


def suggest(keyword: str) -> list[dict]:
    keyword = (keyword or "").strip()[:MAX_SEARCH_LENGTH]
    if not keyword:
        return []
    rank = Case(
        When(name__istartswith=keyword, then=Value(0)),
        default=Value(1),
        output_field=IntegerField(),
    )
    products = (
        _on_sale_products()
        .filter(name__icontains=keyword)
        .annotate(rank=rank)
        .order_by("rank", "-sales_count", "-id")[: settings.CATALOG_SUGGEST_LIMIT]
    )
    return [
        {
            "public_id": product.public_id,
            "name": product.name,
            "price_min": _money(product.price_min),
            "main_image": product.main_image,
        }
        for product in products
    ]


def product_list_item(product: Product) -> dict:
    return {
        "public_id": product.public_id,
        "name": product.name,
        "subtitle": product.subtitle,
        "main_image": product.main_image,
        "price_min": _money(product.price_min),
        "price_max": _money(product.price_max),
        "sales_count": product.sales_count,
        "category": {"public_id": product.category.public_id, "name": product.category.name},
    }


# ---------------------------------------------------------------------------
# 后台
# ---------------------------------------------------------------------------
def admin_category_list():
    return (
        Category.objects.filter(is_deleted=False)
        .select_related("parent")
        .annotate(product_count=Count("products", filter=Q(products__is_deleted=False)))
        .order_by("level", "sort_weight", "id")
    )


def admin_product_queryset(params):
    queryset = (
        Product.objects.filter(is_deleted=False)
        .select_related("category")
        .annotate(
            sku_count=Count("skus", filter=Q(skus__is_deleted=False), distinct=True),
            stock_total=Coalesce(Sum("skus__stock"), 0),
        )
    )
    status = (params.get("status") or "").strip()
    if status:
        queryset = queryset.filter(status=status)
    category_public_id = (params.get("category") or "").strip()
    if category_public_id:
        queryset = queryset.filter(category_id__in=_category_ids(category_public_id))
    search = (params.get("search") or "").strip()[:MAX_SEARCH_LENGTH]
    if search:
        queryset = queryset.filter(name__icontains=search)
    return queryset.order_by("-created_at", "-id")


def get_admin_product(public_id: str) -> Product:
    product = (
        admin_product_queryset({}).prefetch_related("images").filter(public_id=public_id).first()
    )
    if product is None:
        raise BusinessError("PRODUCT_NOT_FOUND", "商品不存在", http_status=404)
    return product
