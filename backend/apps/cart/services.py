"""购物车领域服务：加购、改数量、勾选、删除与清空的唯一写入口。"""

from django.conf import settings
from django.db import transaction

from apps.cart.models import CartItem
from apps.catalog.models import Product, Sku
from apps.common.exceptions import BusinessError


def _max_quantity() -> int:
    return settings.CART_ITEM_MAX_QUANTITY


def _max_items() -> int:
    return settings.CART_MAX_ITEMS


def _validate_quantity(quantity: int) -> None:
    if not isinstance(quantity, int) or not 1 <= quantity <= _max_quantity():
        raise BusinessError(
            "CART_ITEM_LIMIT",
            f"单个商品数量需为 1–{_max_quantity()} 件",
            http_status=422,
            detail={"max_quantity": _max_quantity()},
        )


def _ensure_salable(sku: Sku) -> None:
    """商品与 SKU 均需上架，否则视为失效，禁止加购或改数量。"""
    if sku.is_deleted or sku.product.is_deleted or sku.product.status != Product.Status.ON_SALE:
        raise BusinessError(
            "CART_ITEM_INVALID",
            "商品已下架，无法加入购物车",
            http_status=422,
            detail={"sku_public_id": sku.public_id},
        )
    if sku.status != Sku.Status.ON_SALE:
        raise BusinessError(
            "CART_ITEM_INVALID",
            "该规格已下架，无法加入购物车",
            http_status=422,
            detail={"sku_public_id": sku.public_id},
        )


def _ensure_stock(sku: Sku, quantity: int) -> None:
    if quantity > sku.stock:
        raise BusinessError(
            "CART_STOCK_NOT_ENOUGH",
            "库存不足",
            http_status=422,
            detail={"sku_public_id": sku.public_id, "available": sku.stock},
        )


def _get_locked_sku(sku_public_id: str) -> Sku:
    sku = (
        Sku.objects.select_for_update()
        .select_related("product")
        .filter(public_id=sku_public_id, is_deleted=False)
        .first()
    )
    if sku is None:
        raise BusinessError("PRODUCT_SKU_NOT_FOUND", "SKU 不存在", http_status=404)
    return sku


@transaction.atomic
def add_item(user, sku_public_id: str, quantity: int = 1) -> CartItem:
    """加购：同一 SKU 合并数量；锁 SKU 行保证并发加购不产生重复行。"""
    _validate_quantity(quantity)
    sku = _get_locked_sku(sku_public_id)
    _ensure_salable(sku)
    _ensure_stock(sku, quantity)

    item = CartItem.objects.select_for_update().filter(user=user, sku=sku, is_deleted=False).first()
    if item is not None:
        merged = item.quantity + quantity
        if merged > _max_quantity():
            raise BusinessError(
                "CART_ITEM_LIMIT",
                f"单个商品数量不能超过 {_max_quantity()} 件",
                http_status=422,
                detail={"max_quantity": _max_quantity()},
            )
        _ensure_stock(sku, merged)
        item.quantity = merged
        item.is_selected = True
        item.save(update_fields=["quantity", "is_selected", "updated_at"])
        return item

    if CartItem.objects.filter(user=user, is_deleted=False).count() >= _max_items():
        raise BusinessError(
            "CART_ITEM_LIMIT",
            f"购物车最多添加 {_max_items()} 种商品",
            http_status=422,
            detail={"max_items": _max_items()},
        )

    return CartItem.objects.create(user=user, sku=sku, quantity=quantity)


def get_user_item(user, public_id: str, *, for_update: bool = False) -> CartItem:
    queryset = CartItem.objects.select_related("sku__product")
    if for_update:
        queryset = queryset.select_for_update()
    item = queryset.filter(public_id=public_id, user=user, is_deleted=False).first()
    if item is None:
        raise BusinessError("CART_ITEM_NOT_FOUND", "购物车项不存在", http_status=404)
    return item


@transaction.atomic
def update_item(
    user,
    public_id: str,
    *,
    quantity: int | None = None,
    is_selected: bool | None = None,
) -> CartItem | None:
    """改数量 / 勾选；数量为 0 视为删除，返回 None。"""
    item = get_user_item(user, public_id, for_update=True)
    updated_fields: list[str] = []

    if quantity is not None:
        if quantity == 0:
            item.delete()
            return None
        _validate_quantity(quantity)
        _ensure_salable(item.sku)
        _ensure_stock(item.sku, quantity)
        item.quantity = quantity
        updated_fields.append("quantity")

    if is_selected is not None:
        item.is_selected = is_selected
        updated_fields.append("is_selected")

    if updated_fields:
        item.save(update_fields=[*updated_fields, "updated_at"])
    return item


def delete_item(user, public_id: str) -> None:
    item = get_user_item(user, public_id)
    item.delete()


def clear_cart(user, *, only_selected: bool = False) -> int:
    queryset = CartItem.objects.filter(user=user, is_deleted=False)
    if only_selected:
        queryset = queryset.filter(is_selected=True)
    deleted, _ = queryset.delete()
    return deleted
