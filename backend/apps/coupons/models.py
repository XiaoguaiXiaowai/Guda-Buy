"""优惠券模型（架构文档 7.3 coupons_coupons / coupons_scopes / coupons_user_coupons）。"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel


class Coupon(BaseModel):
    """券模板：类型、门槛、发行量与适用范围；`claimed_quantity` 由 service 原子递增。"""

    class Type(models.TextChoices):
        FIXED = "FIXED", "满减"
        DISCOUNT = "DISCOUNT", "折扣"
        FREE_SHIPPING = "FREE_SHIPPING", "免邮"

    class ScopeType(models.TextChoices):
        ALL = "ALL", "全场"
        CATEGORY = "CATEGORY", "指定分类"
        PRODUCT = "PRODUCT", "指定商品"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "草稿"
        ACTIVE = "ACTIVE", "进行中"
        STOPPED = "STOPPED", "已停止"

    name = models.CharField("券名称", max_length=60)
    coupon_type = models.CharField("券类型", max_length=16, choices=Type.choices)
    value = models.DecimalField(
        "面额/折扣率", max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    min_amount = models.DecimalField(
        "使用门槛", max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_quantity = models.PositiveIntegerField("发行总量", default=0)
    claimed_quantity = models.PositiveIntegerField("已领取量", default=0)
    per_user_limit = models.PositiveIntegerField("每人限领", default=1)
    scope_type = models.CharField(
        "适用范围", max_length=16, choices=ScopeType.choices, default=ScopeType.ALL
    )
    valid_from = models.DateTimeField("生效时间")
    valid_to = models.DateTimeField("失效时间")
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="创建人",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="更新人",
    )

    class Meta:
        db_table = "coupons_coupons"
        verbose_name = "优惠券"
        verbose_name_plural = "优惠券"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "valid_to"], name="idx_coupons_status_valid"),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def is_free_shipping(self) -> bool:
        return self.coupon_type == self.Type.FREE_SHIPPING


class CouponScope(models.Model):
    """券适用范围明细：一行指向一个分类或一个商品，由 service 保证二者只填其一。"""

    coupon = models.ForeignKey(
        Coupon, on_delete=models.CASCADE, related_name="scopes", verbose_name="所属券"
    )
    category = models.ForeignKey(
        "catalog.Category",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="分类",
    )
    product = models.ForeignKey(
        "catalog.Product",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="商品",
    )

    class Meta:
        db_table = "coupons_scopes"
        verbose_name = "券适用范围"
        verbose_name_plural = "券适用范围"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(category__isnull=False, product__isnull=True)
                    | models.Q(category__isnull=True, product__isnull=False)
                ),
                name="ck_coupon_scopes_one_target",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.coupon_id} · {self.category_id or self.product_id}"


class UserCoupon(BaseModel):
    """用户领取记录：UNUSED → LOCKED（下单）→ USED（支付）；取消回到 UNUSED/EXPIRED。"""

    class Status(models.TextChoices):
        UNUSED = "UNUSED", "未使用"
        LOCKED = "LOCKED", "已锁定"
        USED = "USED", "已使用"
        EXPIRED = "EXPIRED", "已过期"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_coupons",
        verbose_name="领取人",
    )
    coupon = models.ForeignKey(
        Coupon, on_delete=models.PROTECT, related_name="user_coupons", verbose_name="券模板"
    )
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.UNUSED)
    claimed_at = models.DateTimeField("领取时间", default=timezone.now)
    used_at = models.DateTimeField("使用时间", null=True, blank=True)
    expires_at = models.DateTimeField("过期时间")
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="locked_coupons",
        verbose_name="核销订单",
    )

    class Meta:
        db_table = "coupons_user_coupons"
        verbose_name = "用户优惠券"
        verbose_name_plural = "用户优惠券"
        ordering = ["-claimed_at", "-id"]
        indexes = [
            models.Index(
                fields=["user", "status", "expires_at"],
                name="idx_coupons_user_status",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(used_at__isnull=True) | models.Q(order__isnull=False),
                name="ck_user_coupons_used_needs_order",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} · {self.coupon_id} · {self.status}"
