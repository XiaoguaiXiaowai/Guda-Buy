"""购物车模型（架构文档 7.2 cart_items）。"""

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class CartItem(BaseModel):
    """登录用户的购物车项：同一用户同一 SKU 只保留一行，数量合并。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart_items",
        verbose_name="所属用户",
    )
    sku = models.ForeignKey(
        "catalog.Sku",
        on_delete=models.CASCADE,
        related_name="cart_items",
        verbose_name="SKU",
    )
    quantity = models.PositiveSmallIntegerField("数量", default=1)
    is_selected = models.BooleanField("是否勾选", default=True)

    class Meta:
        db_table = "cart_items"
        verbose_name = "购物车项"
        verbose_name_plural = "购物车项"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "sku"], name="uk_cart_items_user_sku"),
        ]
        indexes = [
            models.Index(fields=["user", "is_selected"], name="idx_cart_items_user_selected"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} · {self.sku_id} × {self.quantity}"
