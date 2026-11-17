"""订单定时任务：支付超时取消与发货超时自动确认。"""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.orders import services
from apps.orders.models import Order

logger = logging.getLogger("guda.orders")


@shared_task(name="orders.tasks.cancel_timeout_orders")
def cancel_timeout_orders(limit: int | None = None) -> int:
    """每分钟扫描超过支付截止时间的待支付订单；单次处理有上限，可重复执行。"""
    batch_limit = limit or settings.ORDER_BATCH_LIMIT
    order_ids = list(
        Order.objects.filter(
            status=Order.Status.PENDING_PAYMENT,
            pay_expires_at__lt=timezone.now(),
        )
        .order_by("pay_expires_at")
        .values_list("id", flat=True)[:batch_limit]
    )
    cancelled = 0
    for order_id in order_ids:
        try:
            if services.cancel_timeout_order(order_id):
                cancelled += 1
        except Exception:  # noqa: BLE001 - 单笔失败不阻塞批次
            logger.exception(
                "超时取消订单失败 order_id=%s",
                order_id,
                extra={"action": "cancel_timeout_order", "result": "fail"},
            )
    if cancelled:
        logger.info(
            "超时取消订单完成 count=%s",
            cancelled,
            extra={"action": "cancel_timeout_orders", "result": "ok"},
        )
    return cancelled


@shared_task(name="orders.tasks.auto_confirm_orders")
def auto_confirm_orders(limit: int | None = None) -> int:
    """扫描发货超过设定天数的订单并自动确认收货。"""
    batch_limit = limit or settings.ORDER_BATCH_LIMIT
    cutoff = timezone.now() - timedelta(days=settings.ORDER_AUTO_CONFIRM_DAYS)
    order_ids = list(
        Order.objects.filter(status=Order.Status.SHIPPED, shipped_at__lte=cutoff)
        .order_by("shipped_at")
        .values_list("id", flat=True)[:batch_limit]
    )
    confirmed = 0
    for order_id in order_ids:
        try:
            if services.auto_confirm_order(order_id):
                confirmed += 1
        except Exception:  # noqa: BLE001 - 单笔失败不阻塞批次
            logger.exception(
                "自动确认收货失败 order_id=%s",
                order_id,
                extra={"action": "auto_confirm_order", "result": "fail"},
            )
    return confirmed
