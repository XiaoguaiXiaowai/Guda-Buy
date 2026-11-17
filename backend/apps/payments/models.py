"""支付单模型（架构文档 7.4 payments_payments）；I5 仅创建待支付单，支付流程由 I6 接入。"""

from django.db import models

from apps.common.models import BaseModel


class Payment(BaseModel):
    """支付单：金额必须等于订单应付，一个订单可有多张历史支付单。"""

    class Channel(models.TextChoices):
        ALIPAY_MOCK = "ALIPAY_MOCK", "支付宝（模拟）"
        WECHAT_MOCK = "WECHAT_MOCK", "微信（模拟）"
        BALANCE_MOCK = "BALANCE_MOCK", "余额（模拟）"

    class Status(models.TextChoices):
        PENDING = "PENDING", "待支付"
        SUCCESS = "SUCCESS", "支付成功"
        FAILED = "FAILED", "支付失败"
        CLOSED = "CLOSED", "已关闭"

    payment_no = models.CharField("支付单号", max_length=24, unique=True)
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name="对应订单",
    )
    channel = models.CharField(
        "支付渠道", max_length=16, choices=Channel.choices, default=Channel.ALIPAY_MOCK
    )
    amount = models.DecimalField("支付金额", max_digits=12, decimal_places=2)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING)
    paid_at = models.DateTimeField("支付成功时间", null=True, blank=True)
    callback_payload = models.JSONField("回调原文", null=True, blank=True)
    transaction_ref = models.CharField("第三方流水号", max_length=64, blank=True, default="")

    class Meta:
        db_table = "payments_payments"
        verbose_name = "支付单"
        verbose_name_plural = "支付单"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["order", "status"], name="idx_payments_order_status"),
            models.Index(fields=["status", "created_at"], name="idx_payments_status"),
        ]

    def __str__(self) -> str:
        return self.payment_no
