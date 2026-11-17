"""购物车入参校验与出参序列化。"""

from rest_framework import serializers


# ---------------------------------------------------------------------------
# 入参
# ---------------------------------------------------------------------------
class AddCartItemSerializer(serializers.Serializer):
    sku_public_id = serializers.CharField(max_length=32)
    quantity = serializers.IntegerField(min_value=1, max_value=99, default=1)


class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=0, max_value=99, required=False)
    is_selected = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if "quantity" not in attrs and "is_selected" not in attrs:
            raise serializers.ValidationError("quantity 与 is_selected 至少提供一个")
        return attrs


class ClearCartSerializer(serializers.Serializer):
    only_selected = serializers.BooleanField(default=False)


# ---------------------------------------------------------------------------
# 出参
# ---------------------------------------------------------------------------
class CartProductSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    name = serializers.CharField()
    main_image = serializers.CharField()


class CartItemSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    sku_public_id = serializers.CharField()
    sku_code = serializers.CharField()
    spec_text = serializers.CharField()
    specs = serializers.DictField()
    product = CartProductSerializer()
    sale_price = serializers.CharField()
    quantity = serializers.IntegerField()
    is_selected = serializers.BooleanField()
    subtotal = serializers.CharField()
    stock = serializers.IntegerField()
    status = serializers.CharField()
    status_text = serializers.CharField()
    status_reason = serializers.CharField()


class CartSummarySerializer(serializers.Serializer):
    items_count = serializers.IntegerField()
    total_quantity = serializers.IntegerField()
    selected_count = serializers.IntegerField()
    valid_count = serializers.IntegerField()
    items_amount = serializers.CharField()
    can_checkout = serializers.BooleanField()


class CartSerializer(serializers.Serializer):
    items = CartItemSerializer(many=True)
    summary = CartSummarySerializer()


class CartCountSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    total_quantity = serializers.IntegerField()


class CartClearResultSerializer(serializers.Serializer):
    deleted = serializers.IntegerField()
