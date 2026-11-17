"""支付 HTTP 适配层：模拟收银台、回调与后台流水。"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments import selectors, services
from apps.payments.models import Payment
from apps.payments.permissions import CanViewPayments
from apps.payments.serializers import (
    AdminPaymentSerializer,
    MockPayRequestSerializer,
    PaymentCallbackRequestSerializer,
    PaymentCallbackResponseSerializer,
    PaymentCashierSerializer,
    PaymentDetailSerializer,
)

PAYMENT_LIST_PARAMS = [
    OpenApiParameter("order_no", str, description="订单号模糊搜索"),
    OpenApiParameter("payment_no", str, description="支付单号模糊搜索"),
    OpenApiParameter("status", str, description="支付状态：PENDING/SUCCESS/FAILED/CLOSED"),
    OpenApiParameter("channel", str, description="支付渠道"),
    OpenApiParameter("page", int, description="页码，从 1 开始"),
    OpenApiParameter("page_size", int, description="每页条数，最大 100"),
]


class PaymentMockPayView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="发起模拟支付",
        description=(
            "待支付订单发起或复用支付单，返回收银台参数与回调签名；"
            "同渠道复用现有 PENDING 支付单，换渠道关闭旧单后新建。"
        ),
        request=MockPayRequestSerializer,
        responses={200: PaymentCashierSerializer},
    )
    def post(self, request, order_no: str):
        serializer = MockPayRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = services.start_mock_payment(
            request.user,
            order_no=order_no,
            channel=serializer.validated_data["channel"],
        )
        return Response(services.cashier_payload(payment))


class PaymentCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="模拟支付回调",
        description=(
            "公开接口，靠 HMAC-SHA256 签名鉴权。校验支付单、金额、签名后更新支付单与订单；"
            "已成功的支付单重复回调返回 200 且不产生副作用。"
        ),
        request=PaymentCallbackRequestSerializer,
        responses={200: PaymentCallbackResponseSerializer},
    )
    def post(self, request):
        serializer = PaymentCallbackRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = services.handle_callback(serializer.validated_data)
        return Response(
            {
                "payment_no": payment.payment_no,
                "order_no": payment.order.order_no,
                "status": payment.status,
                "status_text": payment.get_status_display(),
                "order_status": payment.order.status,
                "order_status_text": payment.order.get_status_display(),
                "paid_at": payment.paid_at,
            }
        )


class PaymentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="支付单状态查询",
        description="仅本人订单的支付单可见，他人支付单返回 404。",
        responses={200: PaymentDetailSerializer},
    )
    def get(self, request, payment_no: str):
        payment = services.get_user_payment(request.user, payment_no)
        return Response(selectors.payment_payload(payment))


class AdminPaymentListView(generics.GenericAPIView):
    permission_classes = [CanViewPayments]
    serializer_class = AdminPaymentSerializer
    queryset = Payment.objects.none()

    @extend_schema(
        summary="后台支付流水",
        description="运营/管理员查询支付流水，支持订单号、支付单号、状态与渠道筛选。",
        parameters=PAYMENT_LIST_PARAMS,
        responses={200: AdminPaymentSerializer(many=True)},
    )
    def get(self, request):
        queryset = selectors.admin_payment_queryset(request.query_params)
        page = self.paginate_queryset(queryset)
        data = [selectors.admin_payment_brief(payment) for payment in page]
        return self.get_paginated_response(data)
