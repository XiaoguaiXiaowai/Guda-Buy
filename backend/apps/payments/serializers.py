"""支付入参校验与出参序列化（用于 OpenAPI 契约）。"""

from rest_framework import serializers

from apps.payments.models import Payment


class MockPayRequestSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(
        choices=Payment.Channel.choices,
        default=Payment.Channel.ALIPAY_MOCK,
        help_text="模拟支付渠道",
    )


class PaymentCallbackRequestSerializer(serializers.Serializer):
    payment_no = serializers.CharField(max_length=24)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    status = serializers.ChoiceField(
        choices=[("SUCCESS", "成功"), ("FAILED", "失败")],
        help_text="回调目标状态",
    )
    signature = serializers.CharField(max_length=128, help_text="HMAC-SHA256 签名")
    transaction_ref = serializers.CharField(
        max_length=64, required=False, allow_blank=True, default=""
    )


class PaymentCashierSerializer(serializers.Serializer):
    payment_no = serializers.CharField()
    order_no = serializers.CharField()
    channel = serializers.CharField()
    channel_text = serializers.CharField()
    amount = serializers.CharField()
    status = serializers.CharField()
    status_text = serializers.CharField()
    sign = serializers.CharField()
    callback_url = serializers.CharField()
    order_pay_expires_at = serializers.DateTimeField()
    demo_notice = serializers.CharField()


class PaymentDetailSerializer(serializers.Serializer):
    payment_no = serializers.CharField()
    order_no = serializers.CharField()
    channel = serializers.CharField()
    channel_text = serializers.CharField()
    amount = serializers.CharField()
    status = serializers.CharField()
    status_text = serializers.CharField()
    transaction_ref = serializers.CharField(allow_blank=True)
    paid_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class PaymentCallbackResponseSerializer(serializers.Serializer):
    payment_no = serializers.CharField()
    order_no = serializers.CharField()
    status = serializers.CharField()
    status_text = serializers.CharField()
    order_status = serializers.CharField()
    order_status_text = serializers.CharField()
    paid_at = serializers.DateTimeField(allow_null=True)


class AdminPaymentSerializer(PaymentDetailSerializer):
    order_status = serializers.CharField()
    order_status_text = serializers.CharField()
    username = serializers.CharField()
