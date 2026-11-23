"""评价模型（架构文档 7.3 reviews_reviews / reviews_images）。"""

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class Review(BaseModel):
    """订单评价：一单一评（OneToOne），审核通过后才会在前台展示。"""

    class Status(models.TextChoices):
        PENDING = "PENDING", "待审核"
        APPROVED = "APPROVED", "已通过"
        REJECTED = "REJECTED", "已驳回"

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="review",
        verbose_name="关联订单",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviews",
        verbose_name="评价人",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="reviews",
        verbose_name="商品",
    )
    sku = models.ForeignKey(
        "catalog.Sku",
        on_delete=models.PROTECT,
        related_name="reviews",
        verbose_name="SKU",
    )
    rating = models.PositiveSmallIntegerField("评分")
    content = models.CharField("评价内容", max_length=500)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING)
    reject_reason = models.CharField("驳回原因", max_length=100, blank=True, default="")
    is_anonymous = models.BooleanField("匿名评价", default=False)

    class Meta:
        db_table = "reviews_reviews"
        verbose_name = "商品评价"
        verbose_name_plural = "商品评价"
        ordering = ["-created_at", "-id"]
        permissions = [("approve_review", "可审核评价")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="ck_reviews_rating_range",
            ),
        ]
        indexes = [
            models.Index(
                fields=["product", "status", "created_at"],
                name="idx_reviews_product_status",
            ),
            models.Index(fields=["user", "status"], name="idx_reviews_user_status"),
        ]

    def __str__(self) -> str:
        return f"{self.order_id} · {self.rating}"


class ReviewImage(BaseModel):
    """评价图片：单条评价最多 3 张，由 service 校验数量与类型。"""

    review = models.ForeignKey(
        Review, on_delete=models.CASCADE, related_name="images", verbose_name="所属评价"
    )
    image = models.CharField("图片路径", max_length=255)
    sort_order = models.PositiveSmallIntegerField("排序", default=0)

    class Meta:
        db_table = "reviews_images"
        verbose_name = "评价图片"
        verbose_name_plural = "评价图片"
        ordering = ["sort_order", "id"]
        indexes = [models.Index(fields=["review"], name="idx_reviews_images_review")]

    def __str__(self) -> str:
        return f"{self.review_id} · {self.image}"
