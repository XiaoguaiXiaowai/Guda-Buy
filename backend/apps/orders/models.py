"""订单模型（架构文档 7.4 orders_orders / orders_order_items / orders_order_status_logs）。"""

from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class Order(BaseModel):
    """订单主表：金额与收货信息在下单时固化，状态流转只通过 service。"""

    class Status(models.TextChoices):
        PENDING_PAYMENT = "PENDING_PAYMENT", "待支付"
        PAID = "PAID", "已支付"
        SHIPPED = "SHIPPED", "已发货"
        COMPLETED = "COMPLETED", "已完成"
        CANCELLED = "CANCELLED", "已取消"
        REFUNDING = "REFUNDING", "退款中"
        REFUNDED = "REFUNDED", "已退款"

    order_no = models.CharField("订单号", max_length=20, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="下单用户",
    )
    status = models.CharField(
        "状态", max_length=16, choices=Status.choices, default=Status.PENDING_PAYMENT
    )
    items_amount = models.DecimalField("商品小计", max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(
        "优惠金额", max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    shipping_amount = models.DecimalField(
        "运费", max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    payable_amount = models.DecimalField("应付金额", max_digits=12, decimal_places=2)

    # 收货信息快照不可变；address_public_id 仅用于地址删除引用检查
    address_snapshot = models.JSONField("收货信息快照", default=dict)
    address_public_id = models.CharField("下单地址标识", max_length=32, db_index=True)

    pay_expires_at = models.DateTimeField("支付截止时间")
    paid_at = models.DateTimeField("支付时间", null=True, blank=True)
    shipped_at = models.DateTimeField("发货时间", null=True, blank=True)
    completed_at = models.DateTimeField("完成时间", null=True, blank=True)
    cancelled_at = models.DateTimeField("取消时间", null=True, blank=True)
    cancel_reason = models.CharField("取消原因", max_length=100, blank=True, default="")
    tracking_no = models.CharField("运单号", max_length=40, blank=True, default="")
    remark = models.CharField("用户备注", max_length=200, blank=True, default="")

    # 幂等：同一用户同一 key 只允许一单；请求指纹用于识别参数不一致
    idempotency_key = models.CharField("幂等键", max_length=64, null=True, blank=True)
    idempotency_request_hash = models.CharField(
        "幂等请求指纹", max_length=64, blank=True, default=""
    )

    class Meta:
        db_table = "orders_orders"
        verbose_name = "订单"
        verbose_name_plural = "订单"
        ordering = ["-created_at", "-id"]
        permissions = [
            ("view_all_order", "可查看全部订单"),
            ("ship_order", "可发货"),
            ("refund_order", "可发起退款"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "idempotency_key"], name="uk_orders_user_idempotency"
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status"], name="idx_orders_user_status"),
            models.Index(fields=["status", "pay_expires_at"], name="idx_orders_status_expires"),
            models.Index(fields=["status", "shipped_at"], name="idx_orders_status_shipped"),
        ]

    def __str__(self) -> str:
        return self.order_no


class OrderItem(models.Model):
    """订单商品快照：商品名、规格、主图与成交单价下单后不可更新。"""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="items", verbose_name="所属订单"
    )
    sku = models.ForeignKey(
        "catalog.Sku",
        on_delete=models.PROTECT,
        related_name="order_items",
        verbose_name="SKU",
    )
    product_name = models.CharField("商品名称快照", max_length=120)
    sku_spec = models.CharField("规格快照", max_length=60)
    main_image = models.CharField("主图快照", max_length=255, blank=True, default="")
    unit_price = models.DecimalField("成交单价", max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField("数量")
    item_amount = models.DecimalField("小计", max_digits=12, decimal_places=2)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "orders_order_items"
        verbose_name = "订单商品"
        verbose_name_plural = "订单商品"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["order", "sku"], name="uk_order_items_order_sku"),
        ]
        indexes = [models.Index(fields=["order"], name="idx_order_items_order")]

    def __str__(self) -> str:
        return f"{self.order.order_no} · {self.product_name}"


class OrderStatusLog(models.Model):
    """订单状态流水：每次合法状态流转追加一行，禁止修改。"""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="status_logs", verbose_name="所属订单"
    )
    from_status = models.CharField("原状态", max_length=16, blank=True, default="")
    to_status = models.CharField("目标状态", max_length=16)
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="操作人",
    )
    remark = models.CharField("备注", max_length=100, blank=True, default="")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "orders_order_status_logs"
        verbose_name = "订单状态流水"
        verbose_name_plural = "订单状态流水"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.order.order_no} {self.from_status}->{self.to_status}"
