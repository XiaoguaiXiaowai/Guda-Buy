"""评价入参校验与 OpenAPI 出参契约。"""

from rest_framework import serializers


# ---------------------------------------------------------------------------
# 入参
# ---------------------------------------------------------------------------
class ReviewSubmitSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5, help_text="评分 1–5 星")
    content = serializers.CharField(
        min_length=5,
        max_length=500,
        trim_whitespace=True,
        help_text="评价内容 5–500 字",
    )
    is_anonymous = serializers.BooleanField(required=False, default=False)
    sku_public_id = serializers.CharField(
        max_length=32,
        required=False,
        allow_blank=True,
        default="",
        help_text="多商品订单需指定要评价的 SKU",
    )


class ReviewImageUploadSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="jpg/jpeg/png/webp，单张不超过 5MB")


class ReviewRejectSerializer(serializers.Serializer):
    reject_reason = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
        help_text="驳回原因，必填",
    )


# ---------------------------------------------------------------------------
# 出参
# ---------------------------------------------------------------------------
class ReviewImageSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    image = serializers.CharField()
    sort_order = serializers.IntegerField()


class PublicReviewSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    rating = serializers.IntegerField()
    content = serializers.CharField()
    is_anonymous = serializers.BooleanField()
    display_name = serializers.CharField(help_text="昵称；匿名时已脱敏")
    avatar = serializers.CharField(allow_blank=True)
    sku_spec = serializers.CharField()
    images = ReviewImageSerializer(many=True)
    created_at = serializers.DateTimeField()


class OrderReviewSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    order_no = serializers.CharField()
    product_public_id = serializers.CharField()
    product_name = serializers.CharField()
    sku_public_id = serializers.CharField()
    sku_spec = serializers.CharField()
    rating = serializers.IntegerField()
    content = serializers.CharField()
    status = serializers.CharField()
    status_text = serializers.CharField()
    reject_reason = serializers.CharField(allow_blank=True)
    is_anonymous = serializers.BooleanField()
    images = ReviewImageSerializer(many=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class ReviewOrderItemSerializer(serializers.Serializer):
    sku_public_id = serializers.CharField()
    product_name = serializers.CharField()
    sku_spec = serializers.CharField()


class ReviewEligibilitySerializer(serializers.Serializer):
    order_no = serializers.CharField()
    can_review = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True)
    requires_sku = serializers.BooleanField(help_text="多商品订单需指定 SKU")
    items = ReviewOrderItemSerializer(many=True)
    review = OrderReviewSerializer(allow_null=True)
    window_expires_at = serializers.DateTimeField(allow_null=True)


class AdminReviewUserSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    nickname = serializers.CharField()
    username = serializers.CharField()


class AdminReviewProductSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    name = serializers.CharField()


class AdminReviewSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    order_no = serializers.CharField()
    user = AdminReviewUserSerializer()
    product = AdminReviewProductSerializer()
    sku_spec = serializers.CharField()
    rating = serializers.IntegerField()
    content = serializers.CharField()
    status = serializers.CharField()
    status_text = serializers.CharField()
    reject_reason = serializers.CharField(allow_blank=True)
    is_anonymous = serializers.BooleanField()
    images = ReviewImageSerializer(many=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
