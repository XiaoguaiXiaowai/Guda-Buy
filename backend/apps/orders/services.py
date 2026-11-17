"""订单领域服务：结算预览、下单、取消、超时关闭、发货与确认收货的唯一写入口。"""

import hashlib
import json
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.cart.models import CartItem
from apps.catalog import cache as catalog_cache
from apps.catalog.models import Product, Sku
from apps.common.exceptions import BusinessError
from apps.orders.models import Order, OrderItem, OrderStatusLog
from apps.payments import services as payment_services
from apps.payments.models import Payment

UNFINISHED_STATUSES = (
    Order.Status.PENDING_PAYMENT,
    Order.Status.PAID,
    Order.Status.SHIPPED,
)


# ---------------------------------------------------------------------------
# 金额与快照
# ---------------------------------------------------------------------------
def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"))


def _shipping_amount(items_amount: Decimal) -> Decimal:
    threshold = Decimal(settings.ORDER_FREE_SHIPPING_THRESHOLD)
    if items_amount >= threshold:
        return Decimal("0.00")
    return _money(settings.ORDER_SHIPPING_AMOUNT)


def _request_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _address_snapshot(address) -> dict:
    return {
        "address_public_id": address.public_id,
        "receiver_name": address.receiver_name,
        "phone": address.phone,
        "province": address.province,
        "city": address.city,
        "district": address.district,
        "detail": address.detail,
        "postal_code": address.postal_code,
    }


def _get_user_address(user, address_public_id: str):
    address = user.addresses.filter(public_id=address_public_id).first()
    if address is None:
        raise BusinessError("COMMON_NOT_FOUND", "收货地址不存在", http_status=404)
    return address


# ---------------------------------------------------------------------------
# 购物车与库存校验
# ---------------------------------------------------------------------------
def _load_cart_items(user, item_public_ids: list[str]) -> list[CartItem]:
    ids = list(dict.fromkeys(item_public_ids))
    items = list(
        CartItem.objects.filter(user=user, public_id__in=ids, is_deleted=False)
        .select_related("sku__product")
        .order_by("-created_at", "-id")
    )
    if len(items) != len(ids):
        raise BusinessError("CART_ITEM_NOT_FOUND", "购物车项不存在或已删除", http_status=404)
    return items


def _available_stock(sku: Sku) -> int:
    return max(sku.stock - sku.locked_stock, 0)


def _ensure_orderable(sku: Sku, quantity: int) -> None:
    product = sku.product
    if sku.is_deleted or product.is_deleted:
        raise BusinessError(
            "ORDER_STOCK_CHANGED",
            "部分商品已失效，请刷新后重试",
            http_status=422,
            detail={"sku_public_id": sku.public_id, "reason": "商品已失效"},
        )
    if product.status != Product.Status.ON_SALE:
        raise BusinessError(
            "ORDER_STOCK_CHANGED",
            "部分商品已下架，请刷新后重试",
            http_status=422,
            detail={"sku_public_id": sku.public_id, "reason": "商品已下架"},
        )
    if sku.status != Sku.Status.ON_SALE:
        raise BusinessError(
            "ORDER_STOCK_CHANGED",
            "部分规格已下架，请刷新后重试",
            http_status=422,
            detail={"sku_public_id": sku.public_id, "reason": "规格已下架"},
        )
    available = _available_stock(sku)
    if quantity > available:
        raise BusinessError(
            "ORDER_STOCK_CHANGED",
            "库存不足，请刷新后重试",
            http_status=422,
            detail={"sku_public_id": sku.public_id, "available": available},
        )


def _calculate(items: list[CartItem]) -> dict:
    items_amount = Decimal("0.00")
    for item in items:
        items_amount += _money(item.sku.sale_price) * item.quantity
    items_amount = _money(items_amount)
    shipping_amount = _shipping_amount(items_amount)
    return {
        "items_amount": items_amount,
        "discount_amount": Decimal("0.00"),
        "shipping_amount": shipping_amount,
        "payable_amount": _money(items_amount + shipping_amount),
    }


# ---------------------------------------------------------------------------
# 结算预览
# ---------------------------------------------------------------------------
def preview_order(user, *, cart_item_public_ids: list[str], address_public_id: str) -> dict:
    """只读试算：与下单共用金额规则，不锁库存、不写库。"""
    address = _get_user_address(user, address_public_id)
    items = _load_cart_items(user, cart_item_public_ids)
    for item in items:
        _ensure_orderable(item.sku, item.quantity)

    amounts = _calculate(items)
    return {
        "address": _address_snapshot(address),
        "items": [
            {
                "cart_item_public_id": item.public_id,
                "sku_public_id": item.sku.public_id,
                "product_public_id": item.sku.product.public_id,
                "product_name": item.sku.product.name,
                "sku_spec": item.sku.spec_text,
                "main_image": item.sku.product.main_image,
                "unit_price": f"{_money(item.sku.sale_price):.2f}",
                "quantity": item.quantity,
                "item_amount": f"{_money(_money(item.sku.sale_price) * item.quantity):.2f}",
            }
            for item in items
        ],
        **{key: f"{value:.2f}" for key, value in amounts.items()},
        "free_shipping_threshold": f"{_money(settings.ORDER_FREE_SHIPPING_THRESHOLD):.2f}",
    }


# ---------------------------------------------------------------------------
# 下单
# ---------------------------------------------------------------------------
def _generate_order_no() -> str:
    return "GD" + timezone.localtime().strftime("%Y%m%d%H%M%S") + f"{secrets.randbelow(10000):04d}"


def create_order(
    user,
    *,
    cart_item_public_ids: list[str],
    address_public_id: str,
    remark: str,
    idempotency_key: str,
) -> tuple[Order, bool]:
    """下单入口：先查幂等键，再在事务内创建订单、锁库存、建支付单并清理购物车。"""
    fingerprint = _request_hash(
        {
            "cart_item_public_ids": sorted(set(cart_item_public_ids)),
            "address_public_id": address_public_id,
            "remark": remark,
        }
    )

    existing = Order.objects.filter(user=user, idempotency_key=idempotency_key).first()
    if existing is not None:
        if existing.idempotency_request_hash != fingerprint:
            raise BusinessError(
                "ORDER_IDEMPOTENT_REPLAY", "幂等键对应的下单参数不一致", http_status=409
            )
        return existing, False

    try:
        return _create_order_atomic(
            user,
            cart_item_public_ids=cart_item_public_ids,
            address_public_id=address_public_id,
            remark=remark,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        ), True
    except IntegrityError as exc:
        # 并发重复提交：唯一约束兜底，返回已创建的订单
        replay = Order.objects.filter(user=user, idempotency_key=idempotency_key).first()
        if replay is not None and replay.idempotency_request_hash == fingerprint:
            return replay, False
        raise BusinessError(
            "ORDER_IDEMPOTENT_REPLAY", "幂等键对应的下单参数不一致", http_status=409
        ) from exc


@transaction.atomic
def _create_order_atomic(
    user,
    *,
    cart_item_public_ids: list[str],
    address_public_id: str,
    remark: str,
    idempotency_key: str,
    fingerprint: str,
) -> Order:
    address = _get_user_address(user, address_public_id)
    items = _load_cart_items(user, cart_item_public_ids)
    for item in items:
        _ensure_orderable(item.sku, item.quantity)

    # 固定按 SKU id 升序加锁，避免与购物车加购交叉死锁
    sku_ids = sorted({item.sku_id for item in items})
    sku_map = {
        sku.id: sku
        for sku in Sku.objects.select_for_update()
        .select_related("product")
        .filter(id__in=sku_ids)
        .order_by("id")
    }
    quantities: dict[int, int] = {}
    for item in items:
        sku = sku_map[item.sku_id]
        _ensure_orderable(sku, item.quantity)
        quantities[sku.id] = quantities.get(sku.id, 0) + item.quantity

    amounts = _calculate(items)
    order = Order.objects.create(
        order_no=_generate_order_no(),
        user=user,
        status=Order.Status.PENDING_PAYMENT,
        items_amount=amounts["items_amount"],
        discount_amount=amounts["discount_amount"],
        shipping_amount=amounts["shipping_amount"],
        payable_amount=amounts["payable_amount"],
        address_snapshot=_address_snapshot(address),
        address_public_id=address.public_id,
        pay_expires_at=timezone.now() + timedelta(minutes=settings.APP_ORDER_TIMEOUT_MINUTES),
        remark=(remark or "").strip()[:200],
        idempotency_key=idempotency_key,
        idempotency_request_hash=fingerprint,
    )

    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                sku=item.sku,
                product_name=item.sku.product.name,
                sku_spec=item.sku.spec_text,
                main_image=item.sku.product.main_image,
                unit_price=_money(item.sku.sale_price),
                quantity=item.quantity,
                item_amount=_money(_money(item.sku.sale_price) * item.quantity),
            )
            for item in items
        ]
    )

    for sku_id, quantity in quantities.items():
        sku = sku_map[sku_id]
        sku.locked_stock += quantity
        sku.save(update_fields=["locked_stock", "updated_at"])

    OrderStatusLog.objects.create(
        order=order,
        from_status="",
        to_status=Order.Status.PENDING_PAYMENT,
        operator=user,
        remark="创建订单",
    )
    Payment.objects.create(
        payment_no=payment_services.generate_payment_no(order.order_no),
        order=order,
        amount=order.payable_amount,
        status=Payment.Status.PENDING,
    )

    # 只删除本次结算的购物车项，不能清空全部
    CartItem.objects.filter(id__in=[item.id for item in items]).delete()
    return order


# ---------------------------------------------------------------------------
# 取消与库存释放
# ---------------------------------------------------------------------------
def _release_stock(order: Order) -> None:
    quantities: dict[int, int] = {}
    for item in order.items.all():
        quantities[item.sku_id] = quantities.get(item.sku_id, 0) + item.quantity
    if not quantities:
        return
    skus = Sku.objects.select_for_update().filter(id__in=sorted(quantities)).order_by("id")
    for sku in skus:
        sku.locked_stock = max(sku.locked_stock - quantities[sku.id], 0)
        sku.save(update_fields=["locked_stock", "updated_at"])


def _close_pending_payments(order: Order) -> None:
    Payment.objects.filter(order=order, status=Payment.Status.PENDING).update(
        status=Payment.Status.CLOSED,
        updated_at=timezone.now(),
    )


@transaction.atomic
def cancel_order(user, order_no: str, reason: str = "用户取消") -> Order:
    order = Order.objects.select_for_update().filter(order_no=order_no, user=user).first()
    if order is None:
        raise BusinessError("ORDER_NOT_FOUND", "订单不存在", http_status=404)
    if order.status != Order.Status.PENDING_PAYMENT:
        raise BusinessError("ORDER_STATUS_CONFLICT", "当前订单状态不允许取消", http_status=409)

    _release_stock(order)
    _close_pending_payments(order)
    from_status = order.status
    order.status = Order.Status.CANCELLED
    order.cancelled_at = timezone.now()
    order.cancel_reason = (reason or "用户取消")[:100]
    order.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])
    OrderStatusLog.objects.create(
        order=order,
        from_status=from_status,
        to_status=Order.Status.CANCELLED,
        operator=user,
        remark=order.cancel_reason,
    )
    return order


@transaction.atomic
def cancel_timeout_order(order_id: int) -> bool:
    """超时取消：任务幂等，订单已流转时直接跳过。"""
    order = Order.objects.select_for_update().filter(pk=order_id).first()
    if order is None or order.status != Order.Status.PENDING_PAYMENT:
        return False
    if order.pay_expires_at > timezone.now():
        return False

    _release_stock(order)
    _close_pending_payments(order)
    order.status = Order.Status.CANCELLED
    order.cancelled_at = timezone.now()
    order.cancel_reason = "支付超时自动取消"
    order.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])
    OrderStatusLog.objects.create(
        order=order,
        from_status=Order.Status.PENDING_PAYMENT,
        to_status=Order.Status.CANCELLED,
        remark=order.cancel_reason,
    )
    return True


# ---------------------------------------------------------------------------
# 发货、确认收货与自动确认
# ---------------------------------------------------------------------------
@transaction.atomic
def ship_order(order_no: str, tracking_no: str, operator) -> Order:
    order = Order.objects.select_for_update().filter(order_no=order_no).first()
    if order is None:
        raise BusinessError("ORDER_NOT_FOUND", "订单不存在", http_status=404)
    if order.status != Order.Status.PAID:
        raise BusinessError("ORDER_STATUS_CONFLICT", "仅已支付订单可发货", http_status=409)

    order.status = Order.Status.SHIPPED
    order.shipped_at = timezone.now()
    order.tracking_no = tracking_no.strip()
    order.save(update_fields=["status", "shipped_at", "tracking_no", "updated_at"])
    OrderStatusLog.objects.create(
        order=order,
        from_status=Order.Status.PAID,
        to_status=Order.Status.SHIPPED,
        operator=operator,
        remark=f"运单号 {order.tracking_no}",
    )
    return order


def _increase_sales(order: Order) -> None:
    """销量按商品维度累加；确认收货只能成功一次，因此不会重复累加。"""
    counts: dict[int, int] = {}
    for item in order.items.select_related("sku").all():
        product_id = item.sku.product_id
        counts[product_id] = counts.get(product_id, 0) + item.quantity
    if not counts:
        return
    for product_id, quantity in counts.items():
        Product.objects.filter(pk=product_id).update(sales_count=F("sales_count") + quantity)
    catalog_cache.bump_product_version()


def _complete(order: Order, *, operator, remark: str) -> None:
    from_status = order.status
    order.status = Order.Status.COMPLETED
    order.completed_at = timezone.now()
    order.save(update_fields=["status", "completed_at", "updated_at"])
    OrderStatusLog.objects.create(
        order=order,
        from_status=from_status,
        to_status=Order.Status.COMPLETED,
        operator=operator,
        remark=remark,
    )
    _increase_sales(order)


@transaction.atomic
def confirm_order(user, order_no: str) -> Order:
    order = Order.objects.select_for_update().filter(order_no=order_no, user=user).first()
    if order is None:
        raise BusinessError("ORDER_NOT_FOUND", "订单不存在", http_status=404)
    if order.status != Order.Status.SHIPPED:
        raise BusinessError("ORDER_STATUS_CONFLICT", "仅已发货订单可确认收货", http_status=409)
    _complete(order, operator=user, remark="用户确认收货")
    return order


@transaction.atomic
def auto_confirm_order(order_id: int) -> bool:
    """发货 15 天后自动确认；任务可重复执行。"""
    order = Order.objects.select_for_update().filter(pk=order_id).first()
    if order is None or order.status != Order.Status.SHIPPED:
        return False
    cutoff = timezone.now() - timedelta(days=settings.ORDER_AUTO_CONFIRM_DAYS)
    if order.shipped_at is None or order.shipped_at > cutoff:
        return False
    _complete(order, operator=None, remark="发货超时自动确认收货")
    return True
