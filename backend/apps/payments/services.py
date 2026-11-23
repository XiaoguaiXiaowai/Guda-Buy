"""支付领域服务：发起/复用支付单、回调状态机、库存扣减与支付单关闭。

库存口径（I5 交接）：下单只增加 `locked_stock`；支付成功同时扣 `stock` 与 `locked_stock`。
销量不在支付回调中累加，统一由确认收货处理。
"""

import secrets
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Sku
from apps.common.exceptions import BusinessError
from apps.coupons import services as coupon_services
from apps.orders.models import Order, OrderStatusLog
from apps.payments.models import Payment
from apps.payments.signature import sign_payment, verify_payment_signature

CALLBACK_STATUSES = ("SUCCESS", "FAILED")
PAID_ORDER_STATUSES = (
    Order.Status.PAID,
    Order.Status.SHIPPED,
    Order.Status.COMPLETED,
)


def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"))


def generate_payment_no(order_no: str) -> str:
    """支付单号：PAY + 订单号后 17 位 + 4 位序号，共 24 位。"""
    return "PAY" + order_no[-17:] + f"{secrets.randbelow(10000):04d}"


def _generate_transaction_ref() -> str:
    stamp = timezone.localtime().strftime("%Y%m%d%H%M%S")
    return f"MOCK{stamp}{secrets.randbelow(10000):04d}"


def _close_pending_payments(order: Order, *, exclude_id: int | None = None) -> None:
    queryset = Payment.objects.filter(order=order, status=Payment.Status.PENDING)
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    queryset.update(status=Payment.Status.CLOSED, updated_at=timezone.now())


# ---------------------------------------------------------------------------
# 发起支付
# ---------------------------------------------------------------------------
def _ensure_payable(order: Order) -> None:
    if order.status in PAID_ORDER_STATUSES:
        raise BusinessError("PAYMENT_ALREADY_PAID", "订单已支付，无需重复支付", http_status=409)
    if order.status != Order.Status.PENDING_PAYMENT:
        raise BusinessError("PAYMENT_CLOSED", "订单已关闭，无法发起支付", http_status=422)
    if order.pay_expires_at <= timezone.now():
        raise BusinessError("PAYMENT_CLOSED", "订单已超过支付时限", http_status=422)


def start_mock_payment(user, *, order_no: str, channel: str) -> Payment:
    """待支付订单发起模拟支付：同渠道复用 PENDING 单，换渠道则关闭旧单再新建。"""
    if channel not in Payment.Channel.values:
        raise BusinessError("COMMON_VALIDATION_ERROR", "不支持的支付渠道", http_status=400)

    order = Order.objects.filter(order_no=order_no, user=user).first()
    if order is None:
        raise BusinessError("ORDER_NOT_FOUND", "订单不存在", http_status=404)
    if order.status == Order.Status.PENDING_PAYMENT and order.pay_expires_at <= timezone.now():
        # 处于待支付但已超时：先关闭遗留 PENDING 支付单（不开启事务，清理直接落库）
        _close_pending_payments(order)
        raise BusinessError("PAYMENT_CLOSED", "订单已超过支付时限", http_status=422)
    _ensure_payable(order)
    return _start_mock_payment_atomic(order.pk, channel)


@transaction.atomic
def _start_mock_payment_atomic(order_id: int, channel: str) -> Payment:
    order = Order.objects.select_for_update().get(pk=order_id)
    _ensure_payable(order)

    pending = list(
        Payment.objects.select_for_update()
        .filter(order=order, status=Payment.Status.PENDING)
        .order_by("id")
    )
    reused = next(
        (
            payment
            for payment in pending
            if payment.channel == channel and payment.amount == order.payable_amount
        ),
        None,
    )
    if reused is not None:
        _close_pending_payments(order, exclude_id=reused.pk)
        return reused

    _close_pending_payments(order)
    return Payment.objects.create(
        payment_no=generate_payment_no(order.order_no),
        order=order,
        channel=channel,
        amount=order.payable_amount,
        status=Payment.Status.PENDING,
    )


def cashier_payload(payment: Payment) -> dict:
    """返回模拟收银台所需参数；签名供前端模拟回调使用。"""
    return {
        "payment_no": payment.payment_no,
        "order_no": payment.order.order_no,
        "channel": payment.channel,
        "channel_text": payment.get_channel_display(),
        "amount": f"{_money(payment.amount):.2f}",
        "status": payment.status,
        "status_text": payment.get_status_display(),
        "sign": sign_payment(payment.payment_no, payment.amount),
        "callback_url": "/api/v1/payments/callback/",
        "order_pay_expires_at": payment.order.pay_expires_at,
        "demo_notice": "演示支付，不会产生真实扣款",
    }


# ---------------------------------------------------------------------------
# 回调
# ---------------------------------------------------------------------------
def _sanitize_payload(payload: dict) -> dict:
    """回调原文入库前脱敏：不保存签名。"""
    return {
        "payment_no": payload.get("payment_no", ""),
        "amount": f"{_money(payload.get('amount')):.2f}",
        "status": payload.get("status", ""),
        "transaction_ref": (payload.get("transaction_ref") or "")[:64],
    }


def _consume_locked_stock(order: Order) -> None:
    """支付成功：锁定库存转为实际扣减；按 SKU id 升序加锁避免死锁。"""
    quantities: dict[int, int] = {}
    for item in order.items.all():
        quantities[item.sku_id] = quantities.get(item.sku_id, 0) + item.quantity
    if not quantities:
        return
    skus = Sku.objects.select_for_update().filter(id__in=sorted(quantities)).order_by("id")
    for sku in skus:
        quantity = quantities[sku.id]
        sku.stock = max(sku.stock - quantity, 0)
        sku.locked_stock = max(sku.locked_stock - quantity, 0)
        sku.save(update_fields=["stock", "locked_stock", "updated_at"])


@transaction.atomic
def _apply_success(payment_id: int, payload: dict) -> Payment:
    payment = Payment.objects.select_for_update().select_related("order").get(pk=payment_id)
    if payment.status == Payment.Status.SUCCESS:
        return payment
    if payment.status == Payment.Status.CLOSED:
        raise BusinessError("PAYMENT_CLOSED", "支付单已关闭，无法支付", http_status=422)
    if payment.status == Payment.Status.FAILED:
        raise BusinessError(
            "PAYMENT_STATUS_CONFLICT", "支付单已失败，请重新发起支付", http_status=409
        )

    order = Order.objects.select_for_update().get(pk=payment.order_id)
    if order.status == Order.Status.PAID:
        raise BusinessError("PAYMENT_ALREADY_PAID", "订单已支付", http_status=409)
    if order.status != Order.Status.PENDING_PAYMENT:
        raise BusinessError("PAYMENT_CLOSED", "订单已关闭，无法支付", http_status=422)

    now = timezone.now()
    _consume_locked_stock(order)
    coupon_services.mark_used_for_order(order)

    order.status = Order.Status.PAID
    order.paid_at = now
    order.save(update_fields=["status", "paid_at", "updated_at"])

    payment.status = Payment.Status.SUCCESS
    payment.paid_at = now
    payment.transaction_ref = (payload.get("transaction_ref") or "").strip()[
        :64
    ] or _generate_transaction_ref()
    payment.callback_payload = _sanitize_payload(payload)
    payment.save(
        update_fields=[
            "status",
            "paid_at",
            "transaction_ref",
            "callback_payload",
            "updated_at",
        ]
    )

    OrderStatusLog.objects.create(
        order=order,
        from_status=Order.Status.PENDING_PAYMENT,
        to_status=Order.Status.PAID,
        operator=None,
        remark="模拟支付成功",
    )
    _close_pending_payments(order, exclude_id=payment.pk)
    # I8 接入：在 transaction.on_commit 中写入 ORDER_PAID 站内消息
    return payment


@transaction.atomic
def _apply_failure(payment_id: int, payload: dict) -> Payment:
    payment = Payment.objects.select_for_update().select_related("order").get(pk=payment_id)
    if payment.status == Payment.Status.FAILED:
        return payment
    if payment.status == Payment.Status.SUCCESS:
        raise BusinessError(
            "PAYMENT_STATUS_CONFLICT", "支付单已成功，不能置为失败", http_status=409
        )
    if payment.status == Payment.Status.CLOSED:
        raise BusinessError("PAYMENT_CLOSED", "支付单已关闭", http_status=422)
    if payment.order.status != Order.Status.PENDING_PAYMENT:
        raise BusinessError("PAYMENT_CLOSED", "订单已关闭，无法支付", http_status=422)

    payment.status = Payment.Status.FAILED
    payment.transaction_ref = (payload.get("transaction_ref") or "").strip()[
        :64
    ] or _generate_transaction_ref()
    payment.callback_payload = _sanitize_payload(payload)
    payment.save(update_fields=["status", "transaction_ref", "callback_payload", "updated_at"])
    return payment


def handle_callback(payload: dict) -> Payment:
    """回调入口：校验金额与签名后，按目标状态走成功/失败状态机。"""
    payment = (
        Payment.objects.select_related("order")
        .filter(payment_no=payload.get("payment_no", ""))
        .first()
    )
    if payment is None:
        raise BusinessError("PAYMENT_NOT_FOUND", "支付单不存在", http_status=404)

    status = (payload.get("status") or "").upper()
    if status not in CALLBACK_STATUSES:
        raise BusinessError("COMMON_VALIDATION_ERROR", "不支持的回调状态", http_status=400)

    # 先校验金额：金额被篡改时返回 422，而不是签名 401（V6-5）
    amount = _money(payload.get("amount"))
    expected = _money(payment.amount)
    if amount != expected or expected != _money(payment.order.payable_amount):
        raise BusinessError(
            "PAYMENT_AMOUNT_MISMATCH",
            "回调金额与订单应付金额不一致",
            http_status=422,
            detail={"expected": f"{expected:.2f}", "received": f"{amount:.2f}"},
        )

    if not verify_payment_signature(payment.payment_no, amount, payload.get("signature", "")):
        raise BusinessError("PAYMENT_SIGNATURE_INVALID", "回调签名校验失败", http_status=401)

    if status == "SUCCESS":
        _apply_success(payment.pk, payload)
    else:
        _apply_failure(payment.pk, payload)
    return Payment.objects.select_related("order").get(pk=payment.pk)


def get_user_payment(user, payment_no: str) -> Payment:
    payment = (
        Payment.objects.select_related("order")
        .filter(payment_no=payment_no, order__user=user)
        .first()
    )
    if payment is None:
        raise BusinessError("PAYMENT_NOT_FOUND", "支付单不存在", http_status=404)
    return payment
