"""站内消息 HTTP 适配层：列表、未读数、标记已读与全部已读。"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import BusinessError
from apps.notifications import selectors, services
from apps.notifications.models import Notification
from apps.notifications.serializers import (
    NotificationReadResultSerializer,
    NotificationSerializer,
    ReadAllResultSerializer,
    UnreadCountSerializer,
)

NOTIFICATION_LIST_PARAMS = [
    OpenApiParameter(
        "type",
        str,
        description="类型筛选：ORDER_PAID/ORDER_SHIPPED/ORDER_CANCELLED/COUPON_EXPIRING/SYSTEM",
    ),
    OpenApiParameter("page", int, description="页码，从 1 开始"),
    OpenApiParameter("page_size", int, description="每页条数，最大 100"),
]


class NotificationListView(generics.GenericAPIView):
    serializer_class = NotificationSerializer
    queryset = Notification.objects.none()

    @extend_schema(
        summary="我的消息列表",
        description="按创建时间倒序返回站内消息，支持类型筛选与分页；进入消息页不清零未读数。",
        parameters=NOTIFICATION_LIST_PARAMS,
        responses={200: NotificationSerializer(many=True)},
    )
    def get(self, request):
        queryset = selectors.notification_queryset(request.user, request.query_params)
        page = self.paginate_queryset(queryset)
        data = [selectors.notification_payload(notification) for notification in page]
        return self.get_paginated_response(data)


class NotificationUnreadCountView(APIView):
    @extend_schema(
        summary="未读消息数",
        description="按 is_read=False 计数，供前端 30 秒轮询角标使用。",
        responses={200: UnreadCountSerializer},
    )
    def get(self, request):
        return Response({"unread_count": selectors.unread_count(request.user)})


class NotificationReadView(APIView):
    @extend_schema(
        summary="标记消息已读",
        description="仅本人消息可标记；重复标记返回 200 且未读数不会变为负数。",
        request=None,
        responses={200: NotificationReadResultSerializer},
    )
    def post(self, request, public_id: str):
        notification, _ = services.mark_read(request.user, public_id)
        if notification is None:
            raise BusinessError("NOTIFY_NOT_FOUND", "消息不存在", http_status=404)
        return Response(
            {
                "public_id": notification.public_id,
                "is_read": notification.is_read,
                "read_at": notification.read_at,
                "unread_count": selectors.unread_count(request.user),
            }
        )


class NotificationReadAllView(APIView):
    @extend_schema(
        summary="全部标记已读",
        description="一次事务内把本人所有未读消息置为已读，返回本次更新条数。",
        request=None,
        responses={200: ReadAllResultSerializer},
    )
    def post(self, request):
        updated = services.mark_all_read(request.user)
        return Response({"updated": updated, "unread_count": 0})
