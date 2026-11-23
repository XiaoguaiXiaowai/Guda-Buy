"""客服入参校验与 OpenAPI 出参契约。"""

from rest_framework import serializers


# ---------------------------------------------------------------------------
# 入参
# ---------------------------------------------------------------------------
class ConversationCreateSerializer(serializers.Serializer):
    order_no = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        default="",
        help_text="可选，关联本人订单号",
    )


class MessageSendSerializer(serializers.Serializer):
    content = serializers.CharField(
        max_length=1000,
        trim_whitespace=True,
        help_text="纯文本消息，1–1000 字，禁止 HTML",
    )


# ---------------------------------------------------------------------------
# 出参
# ---------------------------------------------------------------------------
class SupportOrderSerializer(serializers.Serializer):
    order_no = serializers.CharField()
    status = serializers.CharField()
    status_text = serializers.CharField()
    payable_amount = serializers.CharField()
    created_at = serializers.DateTimeField()


class SupportUserSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    nickname = serializers.CharField()
    username = serializers.CharField()
    created_at = serializers.DateTimeField()
    last_login_at = serializers.DateTimeField(allow_null=True)


class SupportConversationSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    status = serializers.CharField()
    status_text = serializers.CharField()
    agent_name = serializers.CharField(allow_blank=True)
    order = SupportOrderSerializer(allow_null=True)
    last_message_at = serializers.DateTimeField()
    closed_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class AdminSupportConversationSerializer(SupportConversationSerializer):
    user = SupportUserSerializer()
    agent_public_id = serializers.CharField(allow_blank=True)


class SupportMessageSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    sender_role = serializers.CharField()
    sender_role_text = serializers.CharField()
    sender_name = serializers.CharField()
    content = serializers.CharField()
    is_read = serializers.BooleanField()
    created_at = serializers.DateTimeField()


class SupportMessageListSerializer(serializers.Serializer):
    conversation = SupportConversationSerializer()
    messages = SupportMessageSerializer(many=True)
    next_after = serializers.CharField(allow_blank=True)
