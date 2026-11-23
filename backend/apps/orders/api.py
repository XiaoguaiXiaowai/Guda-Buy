"""订单 HTTP 适配层：仅做协议转换，业务规则在 services。"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import BusinessError
from apps.orders import selectors, services
from apps.orders.models import Order
from apps.orders.permissions import CanShipOrder, IsOrderSupport
from apps.orders.serializers import (
    AdminOrderBriefSerializer,
    OrderBriefSerializer,
    OrderCreateRequestSerializer,
    OrderDetailSerializer,
    OrderPreviewRequestSerializer,
    OrderPreviewSerializer,
    ShipOrderSerializer,
)

ORDER_LIST_PARAMS = [
    OpenApiParameter("status", str, description="订单状态筛选"),
    OpenApiParameter("order_no", str, description="订单号模糊搜索"),
    OpenApiParameter("page", int, description="页码，从 1 开始"),
    OpenApiParameter("page_size", int, description="每页条数，最大 100"),
]

IDEMPOTENCY_KEY_PARAM = OpenApiParameter(
    "Idempotency-Key",
    str,
    location=OpenApiParameter.HEADER,
    required=True,
    description="幂等键，同一用户同一键重复提交返回同一订单",
)


def _idempotency_key(request) -> str:
    key = (request.headers.get("Idempotency-Key") or "").strip()
    if not key or len(key) > 64:
        raise BusinessError(
            "COMMON_VALIDATION_ERROR", "缺少或非法的 Idempotency-Key", http_status=400
        )
    return key


def _fetch_order(order_no: str, *, user=None) -> Order:
    queryset = Order.objects.select_related("user", "user_coupon__coupon").prefetch_related(
        "items__sku", "payments", "status_logs"
    )
    if user is not None:
        queryset = queryset.filter(user=user)
    order = queryset.filter(order_no=order_no).first()
    if order is None:
        raise BusinessError("ORDER_NOT_FOUND", "订单不存在", http_status=404)
    return order


# ---------------------------------------------------------------------------
# 前台
# ---------------------------------------------------------------------------
class OrderPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="结算预览",
        description="按勾选购物车项与收货地址试算商品小计、运费与应付金额（金额为字符串）。",
        request=OrderPreviewRequestSerializer,
        responses={200: OrderPreviewSerializer},
    )
    def post(self, request):
        serializer = OrderPreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = services.preview_order(
            request.user,
            cart_item_public_ids=serializer.validated_data["cart_item_public_ids"],
            address_public_id=serializer.validated_data["address_public_id"],
            user_coupon_public_id=serializer.validated_data.get("user_coupon_public_id", ""),
        )
        return Response(payload)


class OrderListCreateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderBriefSerializer
    queryset = Order.objects.none()

    @extend_schema(
        summary="我的订单列表",
        description="默认按创建时间倒序，支持状态筛选与订单号模糊搜索。",
        parameters=ORDER_LIST_PARAMS,
        responses={200: OrderBriefSerializer(many=True)},
    )
    def get(self, request):
        queryset = selectors.order_queryset(user=request.user, params=request.query_params)
        page = self.paginate_queryset(queryset)
        data = [selectors.order_brief(order) for order in page]
        return self.get_paginated_response(data)

    @extend_schema(
        summary="提交订单",
        description=(
            "请求头需携带 Idempotency-Key；事务内创建订单、锁定库存、生成待支付支付单，"
            "并移除本次结算的购物车项。重复键返回同一订单（200）。"
        ),
        parameters=[IDEMPOTENCY_KEY_PARAM],
        request=OrderCreateRequestSerializer,
        responses={201: OrderDetailSerializer, 200: OrderDetailSerializer},
    )
    def post(self, request):
        serializer = OrderCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order, created = services.create_order(
            request.user,
            cart_item_public_ids=serializer.validated_data["cart_item_public_ids"],
            address_public_id=serializer.validated_data["address_public_id"],
            remark=serializer.validated_data.get("remark", ""),
            idempotency_key=_idempotency_key(request),
            user_coupon_public_id=serializer.validated_data.get("user_coupon_public_id", ""),
        )
        order = _fetch_order(order.order_no, user=request.user)
        payload = selectors.order_detail(order)
        return Response(payload, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="订单详情",
        description="返回商品快照、收货快照、金额明细、支付单与状态流水；他人订单返回 404。",
        responses={200: OrderDetailSerializer},
    )
    def get(self, request, order_no: str):
        order = _fetch_order(order_no, user=request.user)
        return Response(selectors.order_detail(order))


class OrderCancelView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="取消订单",
        description="仅待支付订单可取消；取消后释放锁定库存并关闭待支付支付单。",
        request=None,
        responses={200: OrderDetailSerializer},
    )
    def post(self, request, order_no: str):
        services.cancel_order(request.user, order_no)
        order = _fetch_order(order_no, user=request.user)
        return Response(selectors.order_detail(order))


class OrderConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="确认收货",
        description="仅已发货订单可确认；确认后订单完成并累加商品销量（仅一次）。",
        request=None,
        responses={200: OrderDetailSerializer},
    )
    def post(self, request, order_no: str):
        services.confirm_order(request.user, order_no)
        order = _fetch_order(order_no, user=request.user)
        return Response(selectors.order_detail(order))


# ---------------------------------------------------------------------------
# 后台
# ---------------------------------------------------------------------------
class AdminOrderListView(generics.GenericAPIView):
    permission_classes = [IsOrderSupport]
    serializer_class = AdminOrderBriefSerializer
    queryset = Order.objects.none()

    @extend_schema(
        summary="后台订单查询",
        description="客服、运营、管理员可查看全量订单，支持状态与订单号筛选。",
        parameters=ORDER_LIST_PARAMS,
        responses={200: AdminOrderBriefSerializer(many=True)},
    )
    def get(self, request):
        queryset = selectors.order_queryset(params=request.query_params).select_related("user")
        page = self.paginate_queryset(queryset)
        data = [selectors.order_brief(order, include_user=True) for order in page]
        return self.get_paginated_response(data)


class AdminOrderShipView(APIView):
    permission_classes = [CanShipOrder]

    @extend_schema(
        summary="订单发货",
        description="仅已支付订单可发货；填写运单号后状态转已发货并写入状态流水。",
        request=ShipOrderSerializer,
        responses={200: OrderDetailSerializer},
    )
    def post(self, request, order_no: str):
        serializer = ShipOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.ship_order(order_no, serializer.validated_data["tracking_no"], request.user)
        order = _fetch_order(order_no)
        return Response(selectors.order_detail(order, include_user=True))
