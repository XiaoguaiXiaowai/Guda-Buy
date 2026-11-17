"""支付只读查询与出参组装。"""

from decimal import Decimal

from apps.payments.models import Payment


def _money(value) -> str:
    return f"{Decimal(value or 0):.2f}"


def payment_payload(payment: Payment) -> dict:
    return {
        "payment_no": payment.payment_no,
        "order_no": payment.order.order_no,
        "channel": payment.channel,
        "channel_text": payment.get_channel_display(),
        "amount": _money(payment.amount),
        "status": payment.status,
        "status_text": payment.get_status_display(),
        "transaction_ref": payment.transaction_ref,
        "paid_at": payment.paid_at,
        "created_at": payment.created_at,
    }


def admin_payment_queryset(params):
    queryset = Payment.objects.select_related("order", "order__user")

    order_no = (params.get("order_no") or "").strip()[:20]
    if order_no:
        queryset = queryset.filter(order__order_no__icontains=order_no)

    payment_no = (params.get("payment_no") or "").strip()[:24]
    if payment_no:
        queryset = queryset.filter(payment_no__icontains=payment_no)

    status = (params.get("status") or "").strip().upper()
    if status in Payment.Status.values:
        queryset = queryset.filter(status=status)

    channel = (params.get("channel") or "").strip().upper()
    if channel in Payment.Channel.values:
        queryset = queryset.filter(channel=channel)

    return queryset.order_by("-created_at", "-id")


def admin_payment_brief(payment: Payment) -> dict:
    payload = payment_payload(payment)
    payload.update(
        {
            "order_status": payment.order.status,
            "order_status_text": payment.order.get_status_display(),
            "username": payment.order.user.username,
        }
    )
    return payload
