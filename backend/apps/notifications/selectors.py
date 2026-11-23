"""站内消息只读查询与出参组装。"""

from apps.notifications.models import Notification

NOTIFICATION_TYPE_TEXT = dict(Notification.Type.choices)


def notification_queryset(user, params):
    queryset = Notification.objects.filter(user=user, is_deleted=False)
    notification_type = (params.get("type") or "").strip().upper()
    if notification_type in Notification.Type.values:
        queryset = queryset.filter(type=notification_type)
    return queryset.order_by("-created_at", "-id")


def notification_payload(notification: Notification) -> dict:
    return {
        "public_id": notification.public_id,
        "type": notification.type,
        "type_text": NOTIFICATION_TYPE_TEXT.get(notification.type, notification.type),
        "title": notification.title,
        "content": notification.content,
        "biz_type": notification.biz_type,
        "biz_public_id": notification.biz_public_id,
        "is_read": notification.is_read,
        "read_at": notification.read_at,
        "created_at": notification.created_at,
    }


def unread_count(user) -> int:
    """未读数走数据库计数，避免把整表加载到内存。"""
    return Notification.objects.filter(user=user, is_read=False, is_deleted=False).count()
