"""站内消息出参契约（OpenAPI 用）。"""

from rest_framework import serializers


class NotificationSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    type = serializers.CharField()
    type_text = serializers.CharField()
    title = serializers.CharField()
    content = serializers.CharField()
    biz_type = serializers.CharField()
    biz_public_id = serializers.CharField()
    is_read = serializers.BooleanField()
    read_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class UnreadCountSerializer(serializers.Serializer):
    unread_count = serializers.IntegerField()


class NotificationReadResultSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    is_read = serializers.BooleanField()
    read_at = serializers.DateTimeField(allow_null=True)
    unread_count = serializers.IntegerField()


class ReadAllResultSerializer(serializers.Serializer):
    updated = serializers.IntegerField()
    unread_count = serializers.IntegerField()
