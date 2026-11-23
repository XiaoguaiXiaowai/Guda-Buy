"""优惠券 HTTP 适配层：领券、我的券、结算试算与后台券管理。"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import BusinessError
from apps.coupons import selectors, services
from apps.coupons.models import Coupon
from apps.coupons.permissions import CanManageCoupons
from apps.coupons.serializers import (
    AdminCouponSerializer,
    AvailableCouponSerializer,
    CouponWriteSerializer,
    MyCouponsSerializer,
    OrderCouponTrialSerializer,
    UserCouponSerializer,
)
from apps.orders.models import Order

ADMIN_COUPON_PARAMS = [
    OpenApiParameter("status", str, description="状态：DRAFT/ACTIVE/STOPPED"),
    OpenApiParameter("coupon_type", str, description="类型：FIXED/DISCOUNT/FREE_SHIPPING"),
    OpenApiParameter("keyword", str, description="券名称关键词"),
    OpenApiParameter("page", int, description="页码，从 1 开始"),
    OpenApiParameter("page_size", int, description="每页条数，最大 100"),
]


def _order_lines(order) -> list[dict]:
    return [
        services.make_line(item.sku.product, item.unit_price, item.quantity)
        for item in order.items.select_related("sku__product__category")
    ]


# ---------------------------------------------------------------------------
# 前台
# ---------------------------------------------------------------------------
class AvailableCouponListView(APIView):
    @extend_schema(
        summary="可领取优惠券",
        description="返回进行中且在有效期内的券，附带本人已领数量与是否可领。",
        responses={200: AvailableCouponSerializer(many=True)},
    )
    def get(self, request):
        return Response(selectors.available_coupons(request.user))


class CouponClaimView(APIView):
    @extend_schema(
        summary="领取优惠券",
        description="校验活动状态、有效期、每人限领与总量余量；同一用户重复领取返回 422。",
        request=None,
        responses={201: UserCouponSerializer},
    )
    def post(self, request, public_id: str):
        user_coupon = services.claim_coupon(request.user, public_id)
        return Response(selectors.user_coupon_payload(user_coupon), status=status.HTTP_201_CREATED)


class MyCouponsView(APIView):
    @extend_schema(
        summary="我的优惠券",
        description="按未使用/已使用/已过期分组返回，含使用门槛、有效期与适用范围。",
        responses={200: MyCouponsSerializer},
    )
    def get(self, request):
        return Response(selectors.my_coupons(request.user))


class OrderCouponTrialView(APIView):
    @extend_schema(
        summary="订单可用券试算",
        description="按订单商品试算每张未使用券的适用性、抵扣金额与不可用原因。",
        responses={200: OrderCouponTrialSerializer},
    )
    def get(self, request, order_no: str):
        order = Order.objects.filter(order_no=order_no, user=request.user).first()
        if order is None:
            raise BusinessError("ORDER_NOT_FOUND", "订单不存在", http_status=404)
        result = services.evaluate_coupons_for_user(
            request.user, lines=_order_lines(order), items_amount=order.items_amount
        )
        return Response(
            {
                "order_no": order.order_no,
                "items_amount": f"{order.items_amount:.2f}",
                "coupons": [
                    selectors.evaluation_payload(evaluation) for evaluation in result["evaluations"]
                ],
                "coupon": selectors.order_coupon_payload(order),
            }
        )


# ---------------------------------------------------------------------------
# 后台
# ---------------------------------------------------------------------------
class AdminCouponListCreateView(generics.GenericAPIView):
    permission_classes = [CanManageCoupons]
    serializer_class = AdminCouponSerializer
    queryset = Coupon.objects.none()

    @extend_schema(
        summary="后台券列表",
        description="运营查看券模板，含领取量、使用量与适用范围；支持状态与类型筛选。",
        parameters=ADMIN_COUPON_PARAMS,
        responses={200: AdminCouponSerializer(many=True)},
    )
    def get(self, request):
        queryset = selectors.admin_coupon_queryset(request.query_params)
        page = self.paginate_queryset(queryset)
        data = [selectors.admin_coupon_payload(coupon) for coupon in page]
        return self.get_paginated_response(data)

    @extend_schema(
        summary="创建优惠券",
        description="运营创建券模板与适用范围；非法参数返回明确业务码。",
        request=CouponWriteSerializer,
        responses={201: AdminCouponSerializer},
    )
    def post(self, request):
        serializer = CouponWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        coupon = services.create_coupon(request.user, serializer.validated_data)
        coupon = selectors.admin_coupon_queryset({}).filter(public_id=coupon.public_id).first()
        return Response(selectors.admin_coupon_payload(coupon), status=status.HTTP_201_CREATED)


class AdminCouponDetailView(APIView):
    permission_classes = [CanManageCoupons]

    @extend_schema(
        summary="修改优惠券",
        description="仅未开始发放（领取量为 0）的券可修改；可调整范围、门槛、发行量与状态。",
        request=CouponWriteSerializer,
        responses={200: AdminCouponSerializer},
    )
    def patch(self, request, public_id: str):
        queryset = selectors.admin_coupon_queryset({})
        coupon = queryset.filter(public_id=public_id).first()
        if coupon is None:
            raise BusinessError("COUPON_NOT_FOUND", "优惠券不存在", http_status=404)
        serializer = CouponWriteSerializer(data=request.data, partial=True, instance=coupon)
        serializer.is_valid(raise_exception=True)
        services.update_coupon(request.user, public_id, serializer.validated_data)
        coupon = selectors.admin_coupon_queryset({}).filter(public_id=public_id).first()
        return Response(selectors.admin_coupon_payload(coupon))
