"""站内消息模型（架构文档 7.3 notifications_notifications）。"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel


class Notification(BaseModel):
    """用户站内消息：业务事件写入，用户读取；只由 notifications.services 创建。"""

    class Type(models.TextChoices):
        ORDER_PAID = "ORDER_PAID", "支付成功"
        ORDER_SHIPPED = "ORDER_SHIPPED", "订单发货"
        ORDER_CANCELLED = "ORDER_CANCELLED", "订单取消"
        COUPON_EXPIRING = "COUPON_EXPIRING", "优惠券到期"
        SYSTEM = "SYSTEM", "系统通知"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="接收人",
    )
    type = models.CharField("消息类型", max_length=32, choices=Type.choices)
    title = models.CharField("标题", max_length=60)
    content = models.CharField("正文", max_length=500)
    biz_type = models.CharField("关联业务类型", max_length=32, blank=True, default="")
    biz_public_id = models.CharField("关联业务标识", max_length=32, blank=True, default="")
    is_read = models.BooleanField("是否已读", default=False)
    read_at = models.DateTimeField("已读时间", null=True, blank=True)

    class Meta:
        db_table = "notifications_notifications"
        verbose_name = "站内消息"
        verbose_name_plural = "站内消息"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["user", "is_read", "created_at"],
                name="idx_notifications_user_read",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} · {self.type} · {self.title}"

    def mark_read(self) -> bool:
        """幂等标记已读；已读消息不再更新时间。"""
        if self.is_read:
            return False
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at", "updated_at"])
        return True
