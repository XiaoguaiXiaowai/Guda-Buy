"""客服会话与消息模型（架构文档 7.3 support_conversations / support_messages）。"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel


class SupportConversation(BaseModel):
    """客服会话：WAITING → ACTIVE → CLOSED，同一用户同时只有一个未关闭会话。"""

    class Status(models.TextChoices):
        WAITING = "WAITING", "待接入"
        ACTIVE = "ACTIVE", "进行中"
        CLOSED = "CLOSED", "已关闭"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="support_conversations",
        verbose_name="咨询用户",
    )
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_conversations",
        verbose_name="关联订单",
    )
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_conversations_as_agent",
        verbose_name="接管客服",
    )
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.WAITING)
    last_message_at = models.DateTimeField("最近消息时间", default=timezone.now)
    closed_at = models.DateTimeField("关闭时间", null=True, blank=True)

    class Meta:
        db_table = "support_conversations"
        verbose_name = "客服会话"
        verbose_name_plural = "客服会话"
        ordering = ["-last_message_at", "-id"]
        permissions = [
            ("reply_conversation", "可回复客服会话"),
            ("assign_conversation", "可接管客服会话"),
        ]
        indexes = [
            models.Index(fields=["status", "last_message_at"], name="idx_support_conv_status_time"),
            models.Index(fields=["user", "status"], name="idx_support_conv_user_status"),
        ]

    def __str__(self) -> str:
        return f"{self.public_id} · {self.status}"


class SupportMessage(BaseModel):
    """会话消息：纯文本，按 created_at 升序增量拉取；系统消息 sender 为空。"""

    class SenderRole(models.TextChoices):
        CUSTOMER = "CUSTOMER", "会员"
        AGENT = "AGENT", "客服"
        SYSTEM = "SYSTEM", "系统"

    conversation = models.ForeignKey(
        SupportConversation,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="所属会话",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_messages",
        verbose_name="发送者",
    )
    sender_role = models.CharField("发送者角色", max_length=16, choices=SenderRole.choices)
    content = models.CharField("消息内容", max_length=1000)
    is_read = models.BooleanField("是否已读", default=False)

    class Meta:
        db_table = "support_messages"
        verbose_name = "客服消息"
        verbose_name_plural = "客服消息"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["conversation", "created_at"],
                name="idx_support_msg_conv_created",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.conversation_id} · {self.sender_role}"
