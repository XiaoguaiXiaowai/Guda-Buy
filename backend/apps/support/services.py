"""客服领域服务：会话创建、消息发送、接管、关闭与超时自动关闭的唯一写入口。"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.common.exceptions import BusinessError
from apps.orders.models import Order
from apps.support.models import SupportConversation, SupportMessage
from apps.support.permissions import is_support_staff

logger = logging.getLogger("guda.support")

MESSAGE_MAX_LENGTH = 1000
INCREMENT_LIMIT = 200


def _audit(action: str, target, operator, detail: str = "") -> None:
    """客服操作审计：结构化日志记录动作、对象与操作人。"""
    logger.info(
        "support audit action=%s target=%s operator=%s detail=%s",
        action,
        getattr(target, "public_id", "-"),
        getattr(operator, "public_id", None),
        detail,
        extra={"action": action, "result": "ok"},
    )


def _validate_content(content: str) -> str:
    text = (content or "").strip()
    if not text:
        raise BusinessError("COMMON_VALIDATION_ERROR", "消息内容不能为空")
    if len(text) > MESSAGE_MAX_LENGTH:
        raise BusinessError("COMMON_VALIDATION_ERROR", f"消息内容不能超过 {MESSAGE_MAX_LENGTH} 字")
    if "<" in text or ">" in text:
        raise BusinessError("COMMON_VALIDATION_ERROR", "消息仅支持纯文本，不支持 HTML")
    return text


def _system_message(conversation: SupportConversation, content: str) -> SupportMessage:
    message = SupportMessage.objects.create(
        conversation=conversation,
        sender=None,
        sender_role=SupportMessage.SenderRole.SYSTEM,
        content=content,
    )
    conversation.last_message_at = message.created_at
    conversation.save(update_fields=["last_message_at", "updated_at"])
    return message


@transaction.atomic
def create_conversation(user, order_no: str = "") -> tuple[SupportConversation, bool]:
    """创建会话：同一用户仅一个未关闭会话；已有时直接复用并可按需关联订单。"""
    User.objects.select_for_update().filter(pk=user.pk).first()

    order = None
    if order_no:
        order = Order.objects.filter(order_no=order_no, user=user, is_deleted=False).first()
        if order is None:
            raise BusinessError("ORDER_NOT_FOUND", "订单不存在", http_status=404)

    existing = (
        SupportConversation.objects.select_related("order", "agent")
        .filter(
            user=user,
            status__in=[SupportConversation.Status.WAITING, SupportConversation.Status.ACTIVE],
            is_deleted=False,
        )
        .order_by("-last_message_at", "-id")
        .first()
    )
    if existing is not None:
        if order is not None and existing.order_id is None:
            existing.order = order
            existing.save(update_fields=["order", "updated_at"])
            _audit("support.attach_order", existing, user, order.order_no)
        return existing, False

    conversation = SupportConversation.objects.create(user=user, order=order)
    _audit("support.create", conversation, user, f"order={order_no}")
    return conversation, True


def get_conversation_for_customer(user, public_id: str) -> SupportConversation:
    """会员视角：仅本人会话可见，他人会话按不存在处理。"""
    conversation = (
        SupportConversation.objects.select_related("user", "agent", "order")
        .filter(public_id=public_id, user=user, is_deleted=False)
        .first()
    )
    if conversation is None:
        raise BusinessError("SUPPORT_NOT_PARTICIPANT", "会话不存在或无权访问", http_status=404)
    return conversation


def get_conversation_for_viewer(user, public_id: str) -> SupportConversation:
    """会话详情：本人或客服可读；其他用户按不存在处理。"""
    conversation = (
        SupportConversation.objects.select_related("user", "agent", "order")
        .filter(public_id=public_id, is_deleted=False)
        .first()
    )
    if conversation is None:
        raise BusinessError("SUPPORT_NOT_PARTICIPANT", "会话不存在或无权访问", http_status=404)
    if conversation.user_id != user.pk and not is_support_staff(user):
        raise BusinessError("SUPPORT_NOT_PARTICIPANT", "会话不存在或无权访问", http_status=404)
    return conversation


def list_messages(user, public_id: str, after: str = "") -> tuple[SupportConversation, list]:
    """增量拉取：after 为上一批最后一条消息的 public_id，返回升序消息列表。"""
    conversation = get_conversation_for_viewer(user, public_id)
    queryset = conversation.messages.select_related("sender").order_by("created_at", "id")
    if after:
        anchor = conversation.messages.filter(public_id=after).only("id").first()
        if anchor is None:
            raise BusinessError("COMMON_VALIDATION_ERROR", "增量拉取锚点无效")
        queryset = queryset.filter(id__gt=anchor.id)
    return conversation, list(queryset[:INCREMENT_LIMIT])


@transaction.atomic
def send_message(user, public_id: str, content: str) -> SupportMessage:
    """发送消息：会员仅本人会话；客服需已接管该会话，关闭后双方只读。"""
    text = _validate_content(content)
    conversation = (
        SupportConversation.objects.select_for_update()
        .select_related("user", "agent")
        .filter(public_id=public_id, is_deleted=False)
        .first()
    )
    if conversation is None:
        raise BusinessError("SUPPORT_NOT_PARTICIPANT", "会话不存在或无权访问", http_status=404)

    staff = is_support_staff(user)
    if conversation.user_id == user.pk:
        role = SupportMessage.SenderRole.CUSTOMER
    elif staff:
        if conversation.status == SupportConversation.Status.CLOSED:
            raise BusinessError("SUPPORT_CONVERSATION_CLOSED", "会话已关闭", http_status=409)
        if conversation.status == SupportConversation.Status.WAITING:
            raise BusinessError("SUPPORT_NO_ACTIVE_AGENT", "会话尚未被客服接管", http_status=422)
        if conversation.agent_id != user.pk:
            raise BusinessError("SUPPORT_NOT_PARTICIPANT", "会话已由其他客服接管", http_status=403)
        role = SupportMessage.SenderRole.AGENT
    else:
        raise BusinessError("SUPPORT_NOT_PARTICIPANT", "会话不存在或无权访问", http_status=404)

    if conversation.status == SupportConversation.Status.CLOSED:
        raise BusinessError("SUPPORT_CONVERSATION_CLOSED", "会话已关闭", http_status=409)

    message = SupportMessage.objects.create(
        conversation=conversation,
        sender=user,
        sender_role=role,
        content=text,
    )
    conversation.last_message_at = message.created_at
    conversation.save(update_fields=["last_message_at", "updated_at"])
    _audit("support.send", conversation, user, role)
    return message


def assign_conversation(agent, public_id: str) -> SupportConversation:
    """接管会话：条件更新保证并发下仅一人成功。"""
    now = timezone.now()
    updated = SupportConversation.objects.filter(
        public_id=public_id,
        status=SupportConversation.Status.WAITING,
        is_deleted=False,
    ).update(status=SupportConversation.Status.ACTIVE, agent=agent, updated_at=now)

    conversation = (
        SupportConversation.objects.select_related("user", "agent", "order")
        .filter(public_id=public_id, is_deleted=False)
        .first()
    )
    if conversation is None:
        raise BusinessError("SUPPORT_NOT_PARTICIPANT", "会话不存在", http_status=404)

    if updated == 0:
        if conversation.status == SupportConversation.Status.CLOSED:
            raise BusinessError("SUPPORT_CONVERSATION_CLOSED", "会话已关闭", http_status=409)
        if conversation.agent_id != agent.pk:
            raise BusinessError(
                "SUPPORT_CONVERSATION_TAKEN", "会话已被其他客服接管", http_status=409
            )
        return conversation

    _audit("support.assign", conversation, agent)
    return conversation


@transaction.atomic
def close_conversation(operator, public_id: str, *, auto: bool = False) -> SupportConversation:
    """关闭会话：关闭后双方只读，并写入一条系统消息。重复关闭幂等。"""
    conversation = (
        SupportConversation.objects.select_for_update()
        .select_related("user", "agent", "order")
        .filter(public_id=public_id, is_deleted=False)
        .first()
    )
    if conversation is None:
        raise BusinessError("SUPPORT_NOT_PARTICIPANT", "会话不存在", http_status=404)
    if conversation.status == SupportConversation.Status.CLOSED:
        return conversation

    conversation.status = SupportConversation.Status.CLOSED
    conversation.closed_at = timezone.now()
    conversation.save(update_fields=["status", "closed_at", "updated_at"])
    content = (
        "会话因超过 24 小时无新消息已自动关闭，如有疑问可重新发起咨询。"
        if auto
        else "客服已结束本次会话，如有疑问可重新发起咨询。"
    )
    _system_message(conversation, content)
    _audit("support.auto_close" if auto else "support.close", conversation, operator)
    return conversation


def auto_close_conversation(conversation_id: int) -> bool:
    """定时任务单条处理：仅关闭仍未结束的会话，返回是否本次关闭。"""
    conversation = SupportConversation.objects.filter(pk=conversation_id).only("status").first()
    if conversation is None or conversation.status == SupportConversation.Status.CLOSED:
        return False
    close_conversation(
        operator=None,
        public_id=conversation.public_id,
        auto=True,
    )
    return True


def inactive_cutoff():
    """自动关闭阈值：最近消息时间早于当前时间减去配置小时数。"""
    return timezone.now() - timedelta(hours=settings.SUPPORT_AUTO_CLOSE_HOURS)
