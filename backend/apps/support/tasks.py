"""客服定时任务：24 小时无新消息自动关闭会话。"""

import logging

from celery import shared_task
from django.conf import settings

from apps.support import services
from apps.support.models import SupportConversation

logger = logging.getLogger("guda.support")


@shared_task(
    name="support.tasks.close_inactive_conversations",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def close_inactive_conversations(self, limit: int | None = None) -> int:
    """扫描超时未活跃的未关闭会话，单次处理有上限且可重复执行。"""
    batch_limit = limit or settings.SUPPORT_BATCH_LIMIT
    conversation_ids = list(
        SupportConversation.objects.filter(
            status__in=[SupportConversation.Status.WAITING, SupportConversation.Status.ACTIVE],
            is_deleted=False,
            last_message_at__lt=services.inactive_cutoff(),
        )
        .order_by("last_message_at")
        .values_list("id", flat=True)[:batch_limit]
    )
    closed = 0
    failed = 0
    for conversation_id in conversation_ids:
        try:
            if services.auto_close_conversation(conversation_id):
                closed += 1
        except Exception:  # noqa: BLE001 - 单条失败不阻塞批次
            failed += 1
            logger.exception(
                "自动关闭客服会话失败 conversation_id=%s",
                conversation_id,
                extra={"action": "support.auto_close", "result": "fail"},
            )
    if closed:
        logger.info(
            "客服会话自动关闭完成 count=%s",
            closed,
            extra={"action": "support.close_inactive", "result": "ok"},
        )
    if conversation_ids and failed == len(conversation_ids):
        # 整批异常时交给 Celery 指数退避重试，任务本身幂等
        raise RuntimeError("客服会话自动关闭批次全部失败")
    return closed
