"""订单入参校验与出参序列化。"""

from rest_framework import serializers


# ---------------------------------------------------------------------------
# 入参
# ---------------------------------------------------------------------------
class OrderPreviewRequestSerializer(serializers.Serializer):
    cart_item_public_ids = serializers.ListField(
        child=serializers.CharField(max_length=32),
        allow_empty=False,
        max_length=50,
        help_text="本次结算的购物车项 public_id 列表",
    )
    address_public_id = serializers.CharField(max_length=32)


class OrderCreateRequestSerializer(OrderPreviewRequestSerializer):
    remark = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class ShipOrderSerializer(serializers.Serializer):
    tracking_no = serializers.RegexField(
        r"^[A-Za-z0-9-]{5,40}$",
        error_messages={"invalid": "运单号需为 5–40 位字母、数字或短横线"},
    )


# ---------------------------------------------------------------------------
# 出参
# ---------------------------------------------------------------------------
class OrderAddressSerializer(serializers.Serializer):
    address_public_id = serializers.CharField()
    receiver_name = serializers.CharField()
    phone = serializers.CharField()
    province = serializers.CharField()
    city = serializers.CharField()
    district = serializers.CharField()
    detail = serializers.CharField()
    postal_code = serializers.CharField(allow_blank=True)


class OrderPreviewItemSerializer(serializers.Serializer):
    cart_item_public_id = serializers.CharField()
    sku_public_id = serializers.CharField()
    product_public_id = serializers.CharField()
    product_name = serializers.CharField()
    sku_spec = serializers.CharField()
    main_image = serializers.CharField(allow_blank=True)
    unit_price = serializers.CharField()
    quantity = serializers.IntegerField()
    item_amount = serializers.CharField()


class OrderPreviewSerializer(serializers.Serializer):
    address = OrderAddressSerializer()
    items = OrderPreviewItemSerializer(many=True)
    items_amount = serializers.CharField()
    discount_amount = serializers.CharField()
    shipping_amount = serializers.CharField()
    payable_amount = serializers.CharField()
    free_shipping_threshold = serializers.CharField()


class OrderItemSerializer(serializers.Serializer):
    sku_public_id = serializers.CharField()
    product_public_id = serializers.CharField()
    product_name = serializers.CharField()
    sku_spec = serializers.CharField()
    main_image = serializers.CharField(allow_blank=True)
    unit_price = serializers.CharField()
    quantity = serializers.IntegerField()
    item_amount = serializers.CharField()


class OrderPaymentSerializer(serializers.Serializer):
    payment_no = serializers.CharField()
    channel = serializers.CharField()
    channel_text = serializers.CharField()
    status = serializers.CharField()
    status_text = serializers.CharField()
    amount = serializers.CharField()
    paid_at = serializers.DateTimeField(allow_null=True)


class OrderStatusLogSerializer(serializers.Serializer):
    from_status = serializers.CharField(allow_blank=True)
    from_status_text = serializers.CharField(allow_blank=True)
    to_status = serializers.CharField()
    to_status_text = serializers.CharField()
    remark = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()


class OrderUserSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    username = serializers.CharField()
    nickname = serializers.CharField()
    email = serializers.EmailField()


class OrderBriefSerializer(serializers.Serializer):
    order_no = serializers.CharField()
    status = serializers.CharField()
    status_text = serializers.CharField()
    items_amount = serializers.CharField()
    payable_amount = serializers.CharField()
    total_quantity = serializers.IntegerField()
    items = OrderItemSerializer(many=True)
    created_at = serializers.DateTimeField()
    pay_expires_at = serializers.DateTimeField()
    can_pay = serializers.BooleanField()
    can_cancel = serializers.BooleanField()
    can_confirm = serializers.BooleanField()


class OrderDetailSerializer(OrderBriefSerializer):
    discount_amount = serializers.CharField()
    shipping_amount = serializers.CharField()
    address = OrderAddressSerializer()
    remark = serializers.CharField(allow_blank=True)
    tracking_no = serializers.CharField(allow_blank=True)
    cancel_reason = serializers.CharField(allow_blank=True)
    paid_at = serializers.DateTimeField(allow_null=True)
    shipped_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    cancelled_at = serializers.DateTimeField(allow_null=True)
    payments = OrderPaymentSerializer(many=True)
    status_logs = OrderStatusLogSerializer(many=True)


class AdminOrderBriefSerializer(OrderBriefSerializer):
    user = OrderUserSerializer()
