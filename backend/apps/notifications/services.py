"""站内消息领域服务：消息创建的唯一入口与各业务事件的通知组装。

约定（架构文档 10.8）：所有消息必须经 `create_notification` 写入，业务模块不得直接插表；
消息体不得包含完整手机号、地址等敏感信息；事件回调失败不得影响主事务。
"""

import logging

from django.utils import timezone

from apps.notifications.models import Notification

logger = logging.getLogger("guda.notifications")


def create_notification(
    user,
    *,
    notification_type: str,
    title: str,
    content: str,
    biz_type: str = "",
    biz_public_id: str = "",
) -> Notification:
    """统一创建入口：类型、标题、正文与业务跳转标识。"""
    return Notification.objects.create(
        user=user,
        type=notification_type,
        title=title[:60],
        content=content[:500],
        biz_type=biz_type[:32],
        biz_public_id=biz_public_id[:32],
    )


def _safe_create(user, *, notification_type: str, title: str, content: str, **kwargs):
    """事件驱动的消息写入：异常只记日志，不向调用方（主事务）抛出。"""
    try:
        return create_notification(
            user,
            notification_type=notification_type,
            title=title,
            content=content,
            **kwargs,
        )
    except Exception:  # noqa: BLE001 - 通知失败不得影响业务主流程
        logger.exception(
            "站内消息写入失败 type=%s user_id=%s",
            notification_type,
            getattr(user, "pk", None),
            extra={"action": "create_notification", "result": "error"},
        )
        return None


def _money(value) -> str:
    return f"{value or 0:.2f}"


# ---------------------------------------------------------------------------
# 订单事件
# ---------------------------------------------------------------------------
def notify_order_paid(order) -> Notification | None:
    return _safe_create(
        order.user,
        notification_type=Notification.Type.ORDER_PAID,
        title=f"订单 {order.order_no} 支付成功",
        content=(
            f"你的订单 {order.order_no} 已支付成功，实付 ¥{_money(order.payable_amount)}，"
            "我们会尽快为你安排发货。"
        ),
        biz_type="ORDER",
        biz_public_id=order.order_no,
    )


def notify_order_shipped(order) -> Notification | None:
    tracking = order.tracking_no or "稍后更新"
    return _safe_create(
        order.user,
        notification_type=Notification.Type.ORDER_SHIPPED,
        title=f"订单 {order.order_no} 已发货",
        content=f"你的订单 {order.order_no} 已发货，运单号：{tracking}。",
        biz_type="ORDER",
        biz_public_id=order.order_no,
    )


def notify_order_cancelled(order, *, reason: str = "") -> Notification | None:
    reason_text = (reason or order.cancel_reason or "订单已取消").strip()
    return _safe_create(
        order.user,
        notification_type=Notification.Type.ORDER_CANCELLED,
        title=f"订单 {order.order_no} 已取消",
        content=f"你的订单 {order.order_no} 已取消，原因：{reason_text}。",
        biz_type="ORDER",
        biz_public_id=order.order_no,
    )


# ---------------------------------------------------------------------------
# 优惠券事件
# ---------------------------------------------------------------------------
def notify_coupon_expiring(user_coupon) -> Notification | None:
    """到期提醒：同一张用户券只发一条，重复执行任务不会重复提醒。"""
    exists = Notification.objects.filter(
        user=user_coupon.user,
        type=Notification.Type.COUPON_EXPIRING,
        biz_type="USER_COUPON",
        biz_public_id=user_coupon.public_id,
    ).exists()
    if exists:
        return None
    expires_at = timezone.localtime(user_coupon.expires_at).strftime("%Y-%m-%d %H:%M")
    return _safe_create(
        user_coupon.user,
        notification_type=Notification.Type.COUPON_EXPIRING,
        title="优惠券即将到期",
        content=(
            f"你的「{user_coupon.coupon.name}」将于 {expires_at} 前到期，" "记得在有效期内使用。"
        ),
        biz_type="USER_COUPON",
        biz_public_id=user_coupon.public_id,
    )


# ---------------------------------------------------------------------------
# 用户读取
# ---------------------------------------------------------------------------
def mark_read(user, public_id: str) -> tuple[Notification | None, bool]:
    """标记单条已读：越权/不存在返回 None，重复标记返回 changed=False。"""
    notification = Notification.objects.filter(
        user=user, public_id=public_id, is_deleted=False
    ).first()
    if notification is None:
        return None, False
    return notification, notification.mark_read()


def mark_all_read(user) -> int:
    """全部已读：仅更新未读消息，返回本次更新条数。"""
    now = timezone.now()
    return Notification.objects.filter(user=user, is_read=False, is_deleted=False).update(
        is_read=True, read_at=now, updated_at=now
    )
