"""订单只读查询与出参组装。"""

from decimal import Decimal

from apps.coupons import selectors as coupon_selectors
from apps.orders.models import Order
from apps.payments.models import Payment

STATUS_TEXT = dict(Order.Status.choices)
PAYMENT_STATUS_TEXT = dict(Payment.Status.choices)
PAYMENT_CHANNEL_TEXT = dict(Payment.Channel.choices)


def _money(value) -> str:
    return f"{Decimal(value or 0):.2f}"


def _payment_payload(payment: Payment) -> dict:
    return {
        "payment_no": payment.payment_no,
        "channel": payment.channel,
        "channel_text": PAYMENT_CHANNEL_TEXT.get(payment.channel, payment.channel),
        "status": payment.status,
        "status_text": PAYMENT_STATUS_TEXT.get(payment.status, payment.status),
        "amount": _money(payment.amount),
        "paid_at": payment.paid_at,
    }


def _item_payload(item) -> dict:
    return {
        "sku_public_id": item.sku.public_id,
        "product_public_id": item.sku.product.public_id,
        "product_name": item.product_name,
        "sku_spec": item.sku_spec,
        "main_image": item.main_image,
        "unit_price": _money(item.unit_price),
        "quantity": item.quantity,
        "item_amount": _money(item.item_amount),
    }


def _status_log_payload(log) -> dict:
    return {
        "from_status": log.from_status,
        "from_status_text": STATUS_TEXT.get(log.from_status, ""),
        "to_status": log.to_status,
        "to_status_text": STATUS_TEXT.get(log.to_status, log.to_status),
        "remark": log.remark,
        "created_at": log.created_at,
    }


def order_queryset(*, user=None, params):
    queryset = (
        Order.objects.filter(is_deleted=False)
        .select_related("user_coupon__coupon")
        .prefetch_related("items__sku")
    )
    if user is not None:
        queryset = queryset.filter(user=user)

    status = (params.get("status") or "").strip().upper()
    if status in Order.Status.values:
        queryset = queryset.filter(status=status)

    order_no = (params.get("order_no") or "").strip()[:20]
    if order_no:
        queryset = queryset.filter(order_no__icontains=order_no)

    return queryset.order_by("-created_at", "-id")


def order_brief(order: Order, *, include_user: bool = False) -> dict:
    items = [_item_payload(item) for item in order.items.all()]
    payload = {
        "order_no": order.order_no,
        "status": order.status,
        "status_text": STATUS_TEXT.get(order.status, order.status),
        "items_amount": _money(order.items_amount),
        "payable_amount": _money(order.payable_amount),
        "total_quantity": sum(item["quantity"] for item in items),
        "items": items,
        "created_at": order.created_at,
        "pay_expires_at": order.pay_expires_at,
        "can_pay": order.status == Order.Status.PENDING_PAYMENT,
        "can_cancel": order.status == Order.Status.PENDING_PAYMENT,
        "can_confirm": order.status == Order.Status.SHIPPED,
    }
    if include_user:
        payload["user"] = {
            "public_id": order.user.public_id,
            "username": order.user.username,
            "nickname": order.user.nickname,
            "email": order.user.email,
        }
    return payload


def order_detail(order: Order, *, include_user: bool = False) -> dict:
    payload = order_brief(order, include_user=include_user)
    payload.update(
        {
            "discount_amount": _money(order.discount_amount),
            "shipping_amount": _money(order.shipping_amount),
            "coupon": coupon_selectors.order_coupon_payload(order),
            "address": order.address_snapshot,
            "remark": order.remark,
            "tracking_no": order.tracking_no,
            "cancel_reason": order.cancel_reason,
            "paid_at": order.paid_at,
            "shipped_at": order.shipped_at,
            "completed_at": order.completed_at,
            "cancelled_at": order.cancelled_at,
            "payments": [_payment_payload(payment) for payment in order.payments.all()],
            "status_logs": [_status_log_payload(log) for log in order.status_logs.all()],
        }
    )
    return payload
