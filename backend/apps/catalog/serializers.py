"""商品中心入参校验与出参序列化。"""

import re
from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import Category, Product, ProductImage, Sku

SKU_CODE_PATTERN = re.compile(r"^[A-Z0-9-]{8,32}$")


# ---------------------------------------------------------------------------
# 前台输出
# ---------------------------------------------------------------------------
class CategoryTreeItemSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    name = serializers.CharField()
    sort_weight = serializers.IntegerField()
    product_count = serializers.IntegerField()
    children = serializers.ListField(child=serializers.DictField(), default=list)


class ProductListItemSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    name = serializers.CharField()
    subtitle = serializers.CharField()
    main_image = serializers.CharField()
    price_min = serializers.CharField()
    price_max = serializers.CharField()
    sales_count = serializers.IntegerField()
    category = serializers.DictField()


class SkuPublicSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    sku_code = serializers.CharField()
    spec_text = serializers.CharField()
    specs = serializers.DictField()
    sale_price = serializers.CharField()
    original_price = serializers.CharField(allow_null=True)
    stock = serializers.IntegerField()
    stock_status = serializers.CharField()
    stock_text = serializers.CharField()
    status = serializers.CharField()


class ProductDetailSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    name = serializers.CharField()
    subtitle = serializers.CharField()
    description = serializers.CharField()
    main_image = serializers.CharField()
    price_min = serializers.CharField()
    price_max = serializers.CharField()
    sales_count = serializers.IntegerField()
    category = serializers.DictField()
    images = serializers.ListField(child=serializers.DictField())
    skus = SkuPublicSerializer(many=True)
    review_summary = serializers.DictField()
    created_at = serializers.DateTimeField()


class ProductSuggestSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    name = serializers.CharField()
    price_min = serializers.CharField()
    main_image = serializers.CharField()


# ---------------------------------------------------------------------------
# 后台输出
# ---------------------------------------------------------------------------
class AdminCategorySerializer(serializers.ModelSerializer):
    parent_public_id = serializers.SerializerMethodField()
    product_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Category
        fields = [
            "public_id",
            "name",
            "parent_public_id",
            "level",
            "sort_weight",
            "product_count",
        ]

    def get_parent_public_id(self, obj) -> str | None:
        return obj.parent.public_id if obj.parent_id else None


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["public_id", "image", "sort_order"]


class AdminSkuSerializer(serializers.ModelSerializer):
    stock_status = serializers.CharField(read_only=True)
    stock_text = serializers.CharField(read_only=True)

    class Meta:
        model = Sku
        fields = [
            "public_id",
            "sku_code",
            "spec_text",
            "specs",
            "sale_price",
            "original_price",
            "stock",
            "locked_stock",
            "stock_capacity",
            "status",
            "weight_grams",
            "stock_status",
            "stock_text",
            "created_at",
            "updated_at",
        ]


class AdminProductSerializer(serializers.ModelSerializer):
    category = AdminCategorySerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    sku_count = serializers.IntegerField(read_only=True, default=0)
    stock_total = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Product
        fields = [
            "public_id",
            "name",
            "subtitle",
            "description",
            "main_image",
            "price_min",
            "price_max",
            "sales_count",
            "status",
            "sort_weight",
            "category",
            "images",
            "sku_count",
            "stock_total",
            "created_at",
            "updated_at",
        ]


# ---------------------------------------------------------------------------
# 入参
# ---------------------------------------------------------------------------
class CategoryWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=60)
    parent_public_id = serializers.CharField(max_length=32, required=False, allow_blank=True)
    sort_weight = serializers.IntegerField(required=False, default=0)


class ProductWriteSerializer(serializers.Serializer):
    category_public_id = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=120)
    subtitle = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    description = serializers.CharField(required=False, allow_blank=True, default="")
    main_image = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    sort_weight = serializers.IntegerField(required=False, default=0)


class SkuWriteSerializer(serializers.Serializer):
    sku_code = serializers.CharField(max_length=32)
    spec_text = serializers.CharField(max_length=60)
    specs = serializers.DictField(required=False, default=dict)
    sale_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    original_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    stock = serializers.IntegerField(min_value=0, required=False, default=0)
    stock_capacity = serializers.IntegerField(min_value=0, required=False, default=0)
    weight_grams = serializers.IntegerField(min_value=0, required=False, default=0)
    status = serializers.ChoiceField(
        choices=Sku.Status.choices, required=False, default=Sku.Status.ON_SALE
    )

    def validate_sku_code(self, value: str) -> str:
        value = value.strip().upper()
        if not SKU_CODE_PATTERN.match(value):
            raise serializers.ValidationError("SKU 编码需 8–32 位大写字母、数字或连字符")
        return value

    def validate_spec_text(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("规格描述不能为空")
        return value


class StockAdjustSerializer(serializers.Serializer):
    change = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")


class ProductImageUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
