"""客服查询与出参组装：我的会话、增量消息、后台队列与会话详情。"""

from django.db import models

from apps.support.models import SupportConversation, SupportMessage

STATUS_TEXT = dict(SupportConversation.Status.choices)
ORDER_STATUS_TEXT = {
    "PENDING_PAYMENT": "待支付",
    "PAID": "已支付",
    "SHIPPED": "已发货",
    "COMPLETED": "已完成",
    "CANCELLED": "已取消",
    "REFUNDING": "退款中",
    "REFUNDED": "已退款",
}
ROLE_TEXT = dict(SupportMessage.SenderRole.choices)


def _order_payload(order) -> dict | None:
    if order is None:
        return None
    return {
        "order_no": order.order_no,
        "status": order.status,
        "status_text": ORDER_STATUS_TEXT.get(order.status, order.status),
        "payable_amount": f"{order.payable_amount:.2f}",
        "created_at": order.created_at,
    }


def _user_payload(user) -> dict:
    return {
        "public_id": user.public_id,
        "nickname": user.nickname,
        "username": user.username,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


def message_payload(message: SupportMessage) -> dict:
    sender = message.sender
    if message.sender_role == SupportMessage.SenderRole.SYSTEM:
        sender_name = "系统"
    elif sender is not None:
        sender_name = sender.nickname or sender.username
    else:
        sender_name = ROLE_TEXT.get(message.sender_role, message.sender_role)
    return {
        "public_id": message.public_id,
        "sender_role": message.sender_role,
        "sender_role_text": ROLE_TEXT.get(message.sender_role, message.sender_role),
        "sender_name": sender_name,
        "content": message.content,
        "is_read": message.is_read,
        "created_at": message.created_at,
    }


def conversation_payload(conversation: SupportConversation, *, admin: bool = False) -> dict:
    payload = {
        "public_id": conversation.public_id,
        "status": conversation.status,
        "status_text": STATUS_TEXT.get(conversation.status, conversation.status),
        "agent_name": (
            conversation.agent.nickname or conversation.agent.username
            if conversation.agent is not None
            else ""
        ),
        "order": _order_payload(conversation.order),
        "last_message_at": conversation.last_message_at,
        "closed_at": conversation.closed_at,
        "created_at": conversation.created_at,
    }
    if admin:
        payload["user"] = _user_payload(conversation.user)
        payload["agent_public_id"] = (
            conversation.agent.public_id if conversation.agent is not None else ""
        )
    return payload


def my_conversation_queryset(user):
    return (
        SupportConversation.objects.filter(user=user, is_deleted=False)
        .select_related("order", "agent")
        .order_by("-last_message_at", "-id")
    )


def admin_conversation_queryset(params) -> models.QuerySet:
    queryset = SupportConversation.objects.filter(is_deleted=False).select_related(
        "user", "agent", "order"
    )

    status = (params.get("status") or "").strip().upper()
    if status == "ALL":
        pass
    elif status in SupportConversation.Status.values:
        queryset = queryset.filter(status=status)
    else:
        queryset = queryset.filter(
            status__in=[SupportConversation.Status.WAITING, SupportConversation.Status.ACTIVE]
        )

    keyword = (params.get("keyword") or "").strip()
    if keyword:
        queryset = queryset.filter(
            models.Q(user__nickname__icontains=keyword)
            | models.Q(user__username__icontains=keyword)
            | models.Q(order__order_no__icontains=keyword)
        )
    # 先到先服务：最近消息越早越靠前
    return queryset.order_by("last_message_at", "id")
