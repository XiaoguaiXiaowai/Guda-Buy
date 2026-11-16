"""商品中心模型：分类、SPU、商品图、SKU、库存流水（架构文档 7.3）。"""

from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class Category(BaseModel):
    """两级分类树：level=1 为一级，level=2 为二级；商品只能挂二级。"""

    name = models.CharField("分类名称", max_length=60)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
        verbose_name="上级分类",
    )
    level = models.PositiveSmallIntegerField("层级", default=1)
    sort_weight = models.IntegerField("排序权重", default=0)

    class Meta:
        db_table = "catalog_categories"
        verbose_name = "商品分类"
        verbose_name_plural = "商品分类"
        ordering = ["sort_weight", "id"]
        indexes = [
            models.Index(fields=["parent", "sort_weight"], name="idx_catalog_categories_parent"),
            models.Index(fields=["level", "sort_weight"], name="idx_catalog_categories_level"),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.level = 1 if self.parent_id is None else 2
        super().save(*args, **kwargs)


class Product(BaseModel):
    """SPU：商品主数据，价格区间与销量为冗余字段，由 service 维护。"""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "草稿"
        ON_SALE = "ON_SALE", "在售"
        OFF_SALE = "OFF_SALE", "下架"

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="所属分类",
    )
    name = models.CharField("商品名称", max_length=120)
    subtitle = models.CharField("副标题", max_length=200, blank=True, default="")
    description = models.TextField("商品详情", blank=True, default="")
    main_image = models.CharField("主图", max_length=255, blank=True, default="")
    price_min = models.DecimalField(
        "最低价", max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    price_max = models.DecimalField(
        "最高价", max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    sales_count = models.PositiveIntegerField("销量", default=0)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.DRAFT)
    sort_weight = models.IntegerField("排序权重", default=0)
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
        db_table = "catalog_products"
        verbose_name = "商品"
        verbose_name_plural = "商品"
        ordering = ["-sort_weight", "-id"]
        indexes = [
            models.Index(fields=["category", "status"], name="idx_catalog_products_category"),
            models.Index(fields=["status", "sort_weight"], name="idx_catalog_products_status"),
            models.Index(fields=["name"], name="idx_catalog_products_name"),
        ]

    def __str__(self) -> str:
        return self.name


class ProductImage(BaseModel):
    """商品图集，按 sort_order 升序展示。"""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="所属商品",
    )
    image = models.CharField("图片路径", max_length=255)
    sort_order = models.PositiveIntegerField("排序", default=0)

    class Meta:
        db_table = "catalog_product_images"
        verbose_name = "商品图"
        verbose_name_plural = "商品图"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return self.image


class Sku(BaseModel):
    """最小库存单元：售价、可售库存与锁定库存。"""

    class Status(models.TextChoices):
        ON_SALE = "ON_SALE", "在售"
        OFF_SALE = "OFF_SALE", "下架"

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="skus",
        verbose_name="所属商品",
    )
    sku_code = models.CharField("SKU 编码", max_length=32, unique=True)
    spec_text = models.CharField("规格描述", max_length=60)
    specs = models.JSONField("规格键值", default=dict, blank=True)
    sale_price = models.DecimalField("售价", max_digits=12, decimal_places=2)
    original_price = models.DecimalField(
        "划线价", max_digits=12, decimal_places=2, null=True, blank=True
    )
    stock = models.PositiveIntegerField("可售库存", default=0)
    locked_stock = models.PositiveIntegerField("锁定库存", default=0)
    stock_capacity = models.PositiveIntegerField("库存上限", default=0)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.ON_SALE)
    weight_grams = models.PositiveIntegerField("重量（克）", default=0)

    class Meta:
        db_table = "catalog_skus"
        verbose_name = "SKU"
        verbose_name_plural = "SKU"
        ordering = ["id"]
        permissions = [("change_stock", "可调整库存")]
        indexes = [
            models.Index(fields=["product", "status"], name="idx_catalog_skus_product"),
        ]

    def __str__(self) -> str:
        return f"{self.sku_code} · {self.spec_text}"

    @property
    def stock_status(self) -> str:
        if self.stock <= 0:
            return "OUT_OF_STOCK"
        if self.stock <= settings.CATALOG_LOW_STOCK_THRESHOLD:
            return "LOW"
        return "IN_STOCK"

    @property
    def stock_text(self) -> str:
        if self.stock <= 0:
            return "缺货"
        if self.stock <= settings.CATALOG_LOW_STOCK_THRESHOLD:
            return f"仅剩 {self.stock} 件"
        return "现货"


class StockLog(BaseModel):
    """库存变更流水：每次调整记录操作人、增量与调整前后值。"""

    sku = models.ForeignKey(
        Sku,
        on_delete=models.CASCADE,
        related_name="stock_logs",
        verbose_name="SKU",
    )
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="操作人",
    )
    change = models.IntegerField("增量")
    stock_before = models.PositiveIntegerField("调整前库存")
    stock_after = models.PositiveIntegerField("调整后库存")
    reason = models.CharField("调整原因", max_length=100, blank=True, default="")

    class Meta:
        db_table = "catalog_stock_logs"
        verbose_name = "库存流水"
        verbose_name_plural = "库存流水"
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.sku.sku_code} {self.change:+d}"
