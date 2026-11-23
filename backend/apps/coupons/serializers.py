"""优惠券入参校验与出参结构（供 OpenAPI 契约使用）。"""

from decimal import Decimal

from rest_framework import serializers

from apps.coupons.models import Coupon


class CouponWriteSerializer(serializers.Serializer):
    """创建/修改券模板入参；修改时 `partial=True`，且仅未发放的券允许修改。"""

    name = serializers.CharField(max_length=60)
    coupon_type = serializers.ChoiceField(choices=Coupon.Type.choices)
    value = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    min_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, min_value=Decimal("0")
    )
    total_quantity = serializers.IntegerField(min_value=1, max_value=1_000_000)
    per_user_limit = serializers.IntegerField(min_value=1, max_value=100, required=False, default=1)
    scope_type = serializers.ChoiceField(
        choices=Coupon.ScopeType.choices, required=False, default=Coupon.ScopeType.ALL
    )
    scope_category_public_ids = serializers.ListField(
        child=serializers.CharField(max_length=32), required=False, default=list, max_length=50
    )
    scope_product_public_ids = serializers.ListField(
        child=serializers.CharField(max_length=32), required=False, default=list, max_length=100
    )
    valid_from = serializers.DateTimeField()
    valid_to = serializers.DateTimeField()
    status = serializers.ChoiceField(
        choices=Coupon.Status.choices, required=False, default=Coupon.Status.DRAFT
    )

    def validate(self, attrs):
        instance: Coupon | None = getattr(self, "instance", None)

        def pick(field, default=None):
            if field in attrs:
                return attrs[field]
            return getattr(instance, field, default) if instance else default

        coupon_type = pick("coupon_type")
        value = pick("value")
        if coupon_type == Coupon.Type.FREE_SHIPPING:
            attrs["value"] = Decimal("0.00")
        elif value is None:
            raise serializers.ValidationError({"value": "请填写面额或折扣率"})
        elif coupon_type == Coupon.Type.FIXED and value <= 0:
            raise serializers.ValidationError({"value": "满减金额必须大于 0"})
        elif coupon_type == Coupon.Type.DISCOUNT and not (
            Decimal("0.01") <= value <= Decimal("0.99")
        ):
            raise serializers.ValidationError({"value": "折扣率需在 0.01–0.99 之间"})

        valid_from = pick("valid_from")
        valid_to = pick("valid_to")
        if valid_from and valid_to and valid_from >= valid_to:
            raise serializers.ValidationError({"valid_to": "失效时间必须晚于生效时间"})

        scope_type = pick("scope_type", Coupon.ScopeType.ALL)
        category_ids = attrs.get("scope_category_public_ids")
        product_ids = attrs.get("scope_product_public_ids")
        if instance is not None and category_ids is None and product_ids is None:
            # 修改时未提交范围明细：保持原范围，交给 service 校验是否允许切换类型
            return attrs
        category_ids = category_ids or []
        product_ids = product_ids or []
        if scope_type == Coupon.ScopeType.CATEGORY and (not category_ids or product_ids):
            raise serializers.ValidationError(
                {"scope_category_public_ids": "分类券需且仅需配置分类"}
            )
        if scope_type == Coupon.ScopeType.PRODUCT and (not product_ids or category_ids):
            raise serializers.ValidationError(
                {"scope_product_public_ids": "商品券需且仅需配置商品"}
            )
        if scope_type == Coupon.ScopeType.ALL and (category_ids or product_ids):
            raise serializers.ValidationError({"scope_type": "全场券无需配置适用范围"})
        return attrs

    def create(self, validated_data):  # pragma: no cover - 写操作在 service 完成
        raise NotImplementedError

    def update(self, instance, validated_data):  # pragma: no cover
        raise NotImplementedError


# ---------------------------------------------------------------------------
# 出参
# ---------------------------------------------------------------------------
COUPON_API_FIELDS = {
    "public_id": serializers.CharField(),
    "name": serializers.CharField(),
    "coupon_type": serializers.CharField(),
    "coupon_type_text": serializers.CharField(),
    "value": serializers.CharField(),
    "min_amount": serializers.CharField(),
    "per_user_limit": serializers.IntegerField(),
    "scope_type": serializers.CharField(),
    "scope_text": serializers.CharField(),
    "scope_summary": serializers.CharField(),
    "total_quantity": serializers.IntegerField(),
    "claimed_quantity": serializers.IntegerField(),
    "valid_from": serializers.DateTimeField(),
    "valid_to": serializers.DateTimeField(),
    "status": serializers.CharField(),
    "status_text": serializers.CharField(),
}


CouponBriefSerializer = type("CouponBriefSerializer", (serializers.Serializer,), COUPON_API_FIELDS)


class AvailableCouponSerializer(CouponBriefSerializer):
    claimed_by_me = serializers.IntegerField()
    can_claim = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True)


class CouponEvaluationSerializer(CouponBriefSerializer):
    user_coupon_id = serializers.CharField()
    status_text = serializers.CharField()
    claimed_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    usable = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True)
    eligible_amount = serializers.CharField()
    discount_amount = serializers.CharField()
    shipping_amount = serializers.CharField()
    payable_amount = serializers.CharField()


class UserCouponSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    status = serializers.CharField()
    status_text = serializers.CharField()
    claimed_at = serializers.DateTimeField()
    used_at = serializers.DateTimeField(allow_null=True)
    expires_at = serializers.DateTimeField()
    order_no = serializers.CharField(allow_blank=True)
    coupon = CouponBriefSerializer()


class UserCouponCountsSerializer(serializers.Serializer):
    unused = serializers.IntegerField()
    used = serializers.IntegerField()
    expired = serializers.IntegerField()


class MyCouponsSerializer(serializers.Serializer):
    unused = UserCouponSerializer(many=True)
    used = UserCouponSerializer(many=True)
    expired = UserCouponSerializer(many=True)
    counts = UserCouponCountsSerializer()


class CouponScopeRefSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    name = serializers.CharField()


class AdminCouponSerializer(CouponBriefSerializer):
    used_quantity = serializers.IntegerField()
    scope_categories = CouponScopeRefSerializer(many=True)
    scope_products = CouponScopeRefSerializer(many=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class OrderCouponSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    status = serializers.CharField()
    status_text = serializers.CharField()
    name = serializers.CharField()
    coupon_type = serializers.CharField()
    coupon_type_text = serializers.CharField()
    value = serializers.CharField()


class OrderCouponTrialSerializer(serializers.Serializer):
    order_no = serializers.CharField()
    items_amount = serializers.CharField()
    coupons = CouponEvaluationSerializer(many=True)
    coupon = OrderCouponSerializer(allow_null=True)
