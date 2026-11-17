"""购物车只读查询与金额试算。"""

from decimal import Decimal

from apps.cart.models import CartItem
from apps.catalog.models import Product, Sku

STATUS_VALID = "VALID"
STATUS_INVALID = "INVALID"
STATUS_INSUFFICIENT = "INSUFFICIENT"

STATUS_TEXT = {
    STATUS_VALID: "有效",
    STATUS_INVALID: "已失效",
    STATUS_INSUFFICIENT: "库存不足",
}


def _money(value) -> str:
    return f"{Decimal(value or 0):.2f}"


def _resolve_status(item: CartItem) -> tuple[str, str]:
    """返回 (status, reason)；判定顺序：商品/SKU 下架优先于库存不足。"""
    sku = item.sku
    if sku.is_deleted or sku.product.is_deleted:
        return STATUS_INVALID, "商品已失效"
    if sku.product.status != Product.Status.ON_SALE:
        return STATUS_INVALID, "商品已下架"
    if sku.status != Sku.Status.ON_SALE:
        return STATUS_INVALID, "规格已下架"
    if item.quantity > sku.stock:
        return STATUS_INSUFFICIENT, f"库存仅剩 {sku.stock} 件"
    return STATUS_VALID, ""


def item_payload(item: CartItem) -> dict:
    status, reason = _resolve_status(item)
    subtotal = Decimal(item.sku.sale_price) * item.quantity
    return {
        "public_id": item.public_id,
        "sku_public_id": item.sku.public_id,
        "sku_code": item.sku.sku_code,
        "spec_text": item.sku.spec_text,
        "specs": item.sku.specs,
        "product": {
            "public_id": item.sku.product.public_id,
            "name": item.sku.product.name,
            "main_image": item.sku.product.main_image,
        },
        "sale_price": _money(item.sku.sale_price),
        "quantity": item.quantity,
        "is_selected": item.is_selected,
        "subtotal": _money(subtotal),
        "stock": item.sku.stock,
        "status": status,
        "status_text": STATUS_TEXT[status],
        "status_reason": reason,
    }


def cart_queryset(user):
    return (
        CartItem.objects.filter(user=user, is_deleted=False)
        .select_related("sku__product")
        .order_by("-created_at", "-id")
    )


def cart_payload(user) -> dict:
    items = [item_payload(item) for item in cart_queryset(user)]

    items_amount = Decimal("0.00")
    total_quantity = 0
    selected_count = 0
    valid_count = 0
    for item in items:
        total_quantity += item["quantity"]
        if item["status"] == STATUS_VALID:
            valid_count += 1
        if item["status"] == STATUS_VALID and item["is_selected"]:
            selected_count += 1
            items_amount += Decimal(item["sale_price"]) * item["quantity"]

    return {
        "items": items,
        "summary": {
            "items_count": len(items),
            "total_quantity": total_quantity,
            "selected_count": selected_count,
            "valid_count": valid_count,
            "items_amount": _money(items_amount),
            "can_checkout": selected_count > 0,
        },
    }


def cart_count(user) -> dict:
    total_quantity = 0
    count = 0
    for item in CartItem.objects.filter(user=user, is_deleted=False).only("quantity"):
        count += 1
        total_quantity += item.quantity
    return {"count": count, "total_quantity": total_quantity}
