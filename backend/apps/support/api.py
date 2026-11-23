"""客服 HTTP 适配层：会员会话、增量消息与后台队列、接管、关闭。"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.support import selectors, services
from apps.support.models import SupportConversation
from apps.support.permissions import CanManageSupportConversations
from apps.support.serializers import (
    AdminSupportConversationSerializer,
    ConversationCreateSerializer,
    MessageSendSerializer,
    SupportConversationSerializer,
    SupportMessageListSerializer,
    SupportMessageSerializer,
)

ADMIN_QUEUE_PARAMS = [
    OpenApiParameter("status", str, description="WAITING/ACTIVE/CLOSED/ALL，缺省为未关闭"),
    OpenApiParameter("keyword", str, description="用户昵称、用户名或订单号关键词"),
    OpenApiParameter("page", int, description="页码，从 1 开始"),
    OpenApiParameter("page_size", int, description="每页条数，最大 100"),
]


# ---------------------------------------------------------------------------
# 前台
# ---------------------------------------------------------------------------
class MyConversationListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SupportConversationSerializer
    queryset = SupportConversation.objects.none()

    @extend_schema(
        summary="我的客服会话",
        description="返回本人全部会话，按最近消息时间倒序分页。",
        parameters=[
            OpenApiParameter("page", int, description="页码，从 1 开始"),
            OpenApiParameter("page_size", int, description="每页条数，最大 100"),
        ],
        responses={200: SupportConversationSerializer(many=True)},
    )
    def get(self, request):
        queryset = selectors.my_conversation_queryset(request.user)
        page = self.paginate_queryset(queryset)
        data = [selectors.conversation_payload(item) for item in page]
        return self.get_paginated_response(data)

    @extend_schema(
        summary="发起客服会话",
        description="同一用户仅存在一个未关闭会话，已存在时复用并返回 200；可关联本人订单。",
        request=ConversationCreateSerializer,
        responses={201: SupportConversationSerializer, 200: SupportConversationSerializer},
    )
    def post(self, request):
        serializer = ConversationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation, created = services.create_conversation(
            request.user, serializer.validated_data.get("order_no", "")
        )
        return Response(
            selectors.conversation_payload(conversation),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ConversationMessageView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="会话消息历史",
        description=(
            "本人或客服可读；传入 after（上批最后一条消息 public_id）做增量拉取，按时间升序。"
        ),
        parameters=[OpenApiParameter("after", str, description="上批最后一条消息 public_id")],
        responses={200: SupportMessageListSerializer},
    )
    def get(self, request, public_id: str):
        conversation, messages = services.list_messages(
            request.user, public_id, request.query_params.get("after", "")
        )
        return Response(
            {
                "conversation": selectors.conversation_payload(
                    conversation, admin=not conversation.user_id == request.user.pk
                ),
                "messages": [selectors.message_payload(item) for item in messages],
                "next_after": messages[-1].public_id if messages else "",
            }
        )

    @extend_schema(
        summary="发送客服消息",
        description="会员发送本人会话；客服需已接管该会话。会话关闭后双方只读。",
        request=MessageSendSerializer,
        responses={201: SupportMessageSerializer},
    )
    def post(self, request, public_id: str):
        serializer = MessageSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = services.send_message(
            request.user, public_id, serializer.validated_data["content"]
        )
        return Response(selectors.message_payload(message), status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# 后台
# ---------------------------------------------------------------------------
class AdminConversationListView(generics.GenericAPIView):
    permission_classes = [CanManageSupportConversations]
    serializer_class = AdminSupportConversationSerializer
    queryset = SupportConversation.objects.none()

    @extend_schema(
        summary="客服会话队列",
        description="按最近消息时间升序返回先到先服务队列，支持状态与关键词筛选。",
        parameters=ADMIN_QUEUE_PARAMS,
        responses={200: AdminSupportConversationSerializer(many=True)},
    )
    def get(self, request):
        queryset = selectors.admin_conversation_queryset(request.query_params)
        page = self.paginate_queryset(queryset)
        data = [selectors.conversation_payload(item, admin=True) for item in page]
        return self.get_paginated_response(data)


class AdminConversationAssignView(APIView):
    permission_classes = [CanManageSupportConversations]

    @extend_schema(
        summary="接管客服会话",
        description="仅待接入会话可接管；条件更新保证并发下只有一人成功，其余返回 409。",
        request=None,
        responses={200: AdminSupportConversationSerializer},
    )
    def post(self, request, public_id: str):
        conversation = services.assign_conversation(request.user, public_id)
        return Response(selectors.conversation_payload(conversation, admin=True))


class AdminConversationCloseView(APIView):
    permission_classes = [CanManageSupportConversations]

    @extend_schema(
        summary="关闭客服会话",
        description="关闭后双方只读，并写入一条系统消息；重复关闭幂等返回当前会话。",
        request=None,
        responses={200: AdminSupportConversationSerializer},
    )
    def post(self, request, public_id: str):
        conversation = services.close_conversation(request.user, public_id)
        return Response(selectors.conversation_payload(conversation, admin=True))
