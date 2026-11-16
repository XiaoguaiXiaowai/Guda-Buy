"""商品中心领域服务：分类、商品、SKU、库存与图集的唯一写入口。"""

import logging
import secrets
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Max, Min
from PIL import Image, UnidentifiedImageError

from apps.catalog import cache
from apps.catalog.models import Category, Product, ProductImage, Sku, StockLog
from apps.common.exceptions import BusinessError

logger = logging.getLogger("guda.catalog")

IMAGE_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
IMAGE_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
IMAGE_MAX_BYTES = 5 * 1024 * 1024
IMAGE_MAX_SIDE = 4096


def _invalidate_catalog() -> None:
    cache.bump_category_version()
    cache.bump_product_version()


# ---------------------------------------------------------------------------
# 分类
# ---------------------------------------------------------------------------
def get_category(public_id: str) -> Category:
    category = Category.objects.filter(public_id=public_id, is_deleted=False).first()
    if category is None:
        raise BusinessError("PRODUCT_CATEGORY_NOT_FOUND", "分类不存在", http_status=404)
    return category


def create_category(*, name: str, parent_public_id: str | None = None, sort_weight: int = 0):
    name = (name or "").strip()
    if not 1 <= len(name) <= 60:
        raise BusinessError("COMMON_VALIDATION_ERROR", "分类名称需为 1–60 个字符")

    parent = None
    if parent_public_id:
        parent = get_category(parent_public_id)
        if parent.parent_id is not None:
            raise BusinessError(
                "PRODUCT_CATEGORY_INVALID",
                "分类最多两级，二级分类下不可再建子分类",
                http_status=422,
            )

    category = Category.objects.create(name=name, parent=parent, sort_weight=sort_weight)
    _invalidate_catalog()
    return category


def update_category(public_id: str, data: dict) -> Category:
    category = get_category(public_id)
    if "name" in data:
        name = (data["name"] or "").strip()
        if not 1 <= len(name) <= 60:
            raise BusinessError("COMMON_VALIDATION_ERROR", "分类名称需为 1–60 个字符")
        category.name = name
    if "sort_weight" in data:
        category.sort_weight = data["sort_weight"]
    category.save()
    _invalidate_catalog()
    return category


def delete_category(public_id: str) -> None:
    category = get_category(public_id)
    if category.children.filter(is_deleted=False).exists():
        raise BusinessError(
            "PRODUCT_CATEGORY_NOT_EMPTY", "该分类下存在子分类，无法删除", http_status=409
        )
    if Product.objects.filter(category=category, is_deleted=False).exists():
        raise BusinessError(
            "PRODUCT_CATEGORY_NOT_EMPTY", "该分类下存在商品，无法删除", http_status=409
        )
    category.soft_delete()
    _invalidate_catalog()


# ---------------------------------------------------------------------------
# 商品
# ---------------------------------------------------------------------------
def get_product(public_id: str) -> Product:
    product = (
        Product.objects.filter(public_id=public_id, is_deleted=False)
        .select_related("category")
        .first()
    )
    if product is None:
        raise BusinessError("PRODUCT_NOT_FOUND", "商品不存在", http_status=404)
    return product


def _leaf_category(public_id: str) -> Category:
    category = get_category(public_id)
    if category.level != 2:
        raise BusinessError("PRODUCT_CATEGORY_INVALID", "商品必须挂在二级分类下", http_status=422)
    return category


def create_product(data: dict, operator=None) -> Product:
    payload = dict(data)
    category = _leaf_category(payload.pop("category_public_id"))
    name = (payload.pop("name") or "").strip()
    if not 2 <= len(name) <= 120:
        raise BusinessError("COMMON_VALIDATION_ERROR", "商品名称需为 2–120 个字符")

    product = Product.objects.create(
        category=category,
        name=name,
        status=Product.Status.DRAFT,
        created_by=operator,
        updated_by=operator,
        **payload,
    )
    _invalidate_catalog()
    return product


def update_product(public_id: str, data: dict, operator=None) -> Product:
    product = get_product(public_id)
    payload = dict(data)
    if "category_public_id" in payload:
        product.category = _leaf_category(payload.pop("category_public_id"))
    if "name" in payload:
        name = (payload["name"] or "").strip()
        if not 2 <= len(name) <= 120:
            raise BusinessError("COMMON_VALIDATION_ERROR", "商品名称需为 2–120 个字符")
        product.name = name
        payload.pop("name")
    for key, value in payload.items():
        setattr(product, key, value)
    product.updated_by = operator
    product.save()
    _invalidate_catalog()
    return product


def delete_product(public_id: str) -> None:
    product = get_product(public_id)
    product.soft_delete()
    _invalidate_catalog()


def publish_product(public_id: str, operator=None) -> Product:
    product = get_product(public_id)
    on_sale_skus = product.skus.filter(is_deleted=False, status=Sku.Status.ON_SALE)
    if not on_sale_skus.exists():
        raise BusinessError("PRODUCT_NO_SKU", "商品至少需要一个在售 SKU 才能上架", http_status=422)
    if product.status == Product.Status.ON_SALE:
        return product

    with transaction.atomic():
        product.status = Product.Status.ON_SALE
        product.updated_by = operator
        product.save(update_fields=["status", "updated_by", "updated_at"])
        refresh_price_range(product)
    _invalidate_catalog()
    return product


def unpublish_product(public_id: str, operator=None) -> Product:
    product = get_product(public_id)
    if product.status != Product.Status.ON_SALE:
        raise BusinessError("PRODUCT_STATUS_CONFLICT", "仅上架商品可下架", http_status=409)
    product.status = Product.Status.OFF_SALE
    product.updated_by = operator
    product.save(update_fields=["status", "updated_by", "updated_at"])
    _invalidate_catalog()
    return product


def refresh_price_range(product: Product) -> None:
    """按在售 SKU 聚合价格区间（冗余字段由 service 维护）。"""
    aggregate = product.skus.filter(is_deleted=False, status=Sku.Status.ON_SALE).aggregate(
        low=Min("sale_price"), high=Max("sale_price")
    )
    product.price_min = aggregate["low"] or Decimal("0.00")
    product.price_max = aggregate["high"] or Decimal("0.00")
    product.save(update_fields=["price_min", "price_max", "updated_at"])


# ---------------------------------------------------------------------------
# SKU 与库存
# ---------------------------------------------------------------------------
def get_sku(public_id: str) -> Sku:
    sku = (
        Sku.objects.filter(public_id=public_id, is_deleted=False).select_related("product").first()
    )
    if sku is None:
        raise BusinessError("PRODUCT_SKU_NOT_FOUND", "SKU 不存在", http_status=404)
    return sku


def _ensure_sku_code_available(sku_code: str, exclude_pk: int | None = None) -> str:
    sku_code = (sku_code or "").strip().upper()
    exists = Sku.objects.filter(sku_code=sku_code)
    if exclude_pk is not None:
        exists = exists.exclude(pk=exclude_pk)
    if exists.exists():
        raise BusinessError("PRODUCT_SKU_CODE_EXISTS", "SKU 编码已存在", http_status=409)
    return sku_code


def create_sku(product: Product, data: dict) -> Sku:
    payload = dict(data)
    sku_code = _ensure_sku_code_available(payload.pop("sku_code"))
    stock = payload.get("stock", 0)
    locked = payload.get("locked_stock", 0)
    capacity = payload.get("stock_capacity") or stock
    if stock < 0 or locked < 0 or stock + locked > capacity:
        raise BusinessError(
            "PRODUCT_STOCK_INVALID", "库存与锁定库存之和不得超过库存上限", http_status=422
        )
    payload["stock_capacity"] = capacity
    sku = Sku.objects.create(product=product, sku_code=sku_code, **payload)
    refresh_price_range(product)
    _invalidate_catalog()
    return sku


def update_sku(public_id: str, data: dict) -> Sku:
    sku = get_sku(public_id)
    payload = dict(data)
    if "sku_code" in payload:
        sku.sku_code = _ensure_sku_code_available(payload.pop("sku_code"), exclude_pk=sku.pk)

    new_status = payload.get("status", sku.status)
    if (
        sku.product.status == Product.Status.ON_SALE
        and sku.status == Sku.Status.ON_SALE
        and new_status == Sku.Status.OFF_SALE
        and not sku.product.skus.filter(is_deleted=False, status=Sku.Status.ON_SALE)
        .exclude(pk=sku.pk)
        .exists()
    ):
        raise BusinessError(
            "PRODUCT_STATUS_CONFLICT", "在售商品至少保留一个在售 SKU", http_status=409
        )

    capacity = payload.get("stock_capacity", sku.stock_capacity)
    stock = payload.get("stock", sku.stock)
    locked = payload.get("locked_stock", sku.locked_stock)
    if stock + locked > capacity:
        raise BusinessError(
            "PRODUCT_STOCK_INVALID", "库存与锁定库存之和不得超过库存上限", http_status=422
        )

    for key, value in payload.items():
        setattr(sku, key, value)
    sku.save()
    refresh_price_range(sku.product)
    _invalidate_catalog()
    return sku


def adjust_stock(sku_public_id: str, change: int, reason: str = "", operator=None) -> Sku:
    """库存调整只允许增量：单次增加、校验上限、写流水并记录操作人。"""
    if not isinstance(change, int) or change <= 0:
        raise BusinessError("PRODUCT_STOCK_INVALID", "库存调整仅支持正整数增量", http_status=422)

    with transaction.atomic():
        sku = (
            Sku.objects.select_for_update()
            .filter(public_id=sku_public_id, is_deleted=False)
            .first()
        )
        if sku is None:
            raise BusinessError("PRODUCT_SKU_NOT_FOUND", "SKU 不存在", http_status=404)

        before = sku.stock
        after = before + change
        if after + sku.locked_stock > sku.stock_capacity:
            raise BusinessError(
                "PRODUCT_STOCK_INVALID",
                f"调整后库存将超过上限 {sku.stock_capacity}",
                http_status=422,
            )

        sku.stock = after
        sku.save(update_fields=["stock", "updated_at"])
        StockLog.objects.create(
            sku=sku,
            operator=operator,
            change=change,
            stock_before=before,
            stock_after=after,
            reason=(reason or "").strip()[:100],
        )
    logger.info(
        "库存调整 sku=%s change=%+d stock=%d->%d operator=%s",
        sku.sku_code,
        change,
        before,
        after,
        getattr(operator, "public_id", None),
        extra={"action": "adjust_stock", "result": "ok"},
    )
    refresh_price_range(sku.product)
    _invalidate_catalog()
    return sku


# ---------------------------------------------------------------------------
# 商品图集
# ---------------------------------------------------------------------------
def save_product_image(product_public_id: str, uploaded_file) -> ProductImage:
    product = get_product(product_public_id)
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

    content = uploaded_file.read()
    suffix = "jpg" if extension == "jpeg" else extension
    relative_path = f"products/{product.public_id}/{secrets.token_hex(8)}.{suffix}"
    saved_path = default_storage.save(relative_path, ContentFile(content))

    sort_order = (product.images.aggregate(max_order=Max("sort_order"))["max_order"] or 0) + 1
    image_row = ProductImage.objects.create(
        product=product, image=saved_path, sort_order=sort_order
    )
    if not product.main_image:
        product.main_image = saved_path
        product.save(update_fields=["main_image", "updated_at"])
    _invalidate_catalog()
    return image_row


def delete_product_image(product_public_id: str, image_public_id: str) -> None:
    product = get_product(product_public_id)
    image = product.images.filter(public_id=image_public_id).first()
    if image is None:
        raise BusinessError("COMMON_NOT_FOUND", "商品图不存在", http_status=404)

    path = image.image
    image.delete()
    if path:
        default_storage.delete(path)
    if product.main_image == path:
        fallback = product.images.order_by("sort_order", "id").first()
        product.main_image = fallback.image if fallback else ""
        product.save(update_fields=["main_image", "updated_at"])
    _invalidate_catalog()
