"""优惠券定时任务：过期置位与到期前提醒。"""

import logging

from celery import shared_task
from django.conf import settings

from apps.coupons import services
from apps.notifications import services as notification_services

logger = logging.getLogger("guda.coupons")


@shared_task(name="coupons.tasks.expire_user_coupons")
def expire_user_coupons(limit: int | None = None) -> int:
    """每日执行：未使用且已过期的券置 EXPIRED，可重复执行。"""
    count = services.expire_user_coupons(limit)
    if count:
        logger.info(
            "优惠券过期处理完成 count=%s",
            count,
            extra={"action": "expire_user_coupons", "result": "ok"},
        )
    return count


@shared_task(name="coupons.tasks.remind_expiring_coupons")
def remind_expiring_coupons(days: int | None = None) -> int:
    """扫描 N 天内到期的未使用券，逐张写入 COUPON_EXPIRING 站内消息（同券只提醒一次）。"""
    window = days or settings.COUPON_EXPIRING_DAYS
    user_coupons = services.expiring_user_coupons(window)
    created = 0
    for user_coupon in user_coupons:
        if notification_services.notify_coupon_expiring(user_coupon) is not None:
            created += 1
    if user_coupons:
        logger.info(
            "优惠券到期提醒已发送 created=%s candidates=%s days=%s",
            created,
            len(user_coupons),
            window,
            extra={"action": "remind_expiring_coupons", "result": "ok"},
        )
    return created
