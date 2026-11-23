"""评价 HTTP 适配层：商品评价列表、订单评价、图片上传与后台审核。"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Product
from apps.common.exceptions import BusinessError
from apps.reviews import selectors, services
from apps.reviews.models import Review
from apps.reviews.permissions import CanManageReviews
from apps.reviews.serializers import (
    AdminReviewSerializer,
    PublicReviewSerializer,
    ReviewEligibilitySerializer,
    ReviewImageSerializer,
    ReviewImageUploadSerializer,
    ReviewRejectSerializer,
    ReviewSubmitSerializer,
)

ADMIN_REVIEW_PARAMS = [
    OpenApiParameter("status", str, description="状态：PENDING/APPROVED/REJECTED"),
    OpenApiParameter("rating", int, description="星级：1–5"),
    OpenApiParameter("keyword", str, description="订单号、商品名或评价内容关键词"),
    OpenApiParameter("page", int, description="页码，从 1 开始"),
    OpenApiParameter("page_size", int, description="每页条数，最大 100"),
]


# ---------------------------------------------------------------------------
# 前台
# ---------------------------------------------------------------------------
class ProductReviewListView(generics.GenericAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = PublicReviewSerializer
    queryset = Review.objects.none()

    @extend_schema(
        summary="商品评价列表",
        description="仅返回审核通过的评价，按时间倒序分页；匿名评价昵称脱敏且不含用户名。",
        parameters=[
            OpenApiParameter("page", int, description="页码，从 1 开始"),
            OpenApiParameter("page_size", int, description="每页条数，最大 100"),
        ],
        responses={200: PublicReviewSerializer(many=True)},
    )
    def get(self, request, public_id: str):  # noqa: ARG002
        if not Product.objects.filter(public_id=public_id, is_deleted=False).exists():
            raise BusinessError("PRODUCT_NOT_FOUND", "商品不存在", http_status=404)
        queryset = selectors.public_review_queryset(public_id)
        page = self.paginate_queryset(queryset)
        data = [selectors.public_review_payload(review) for review in page]
        return self.get_paginated_response(data)


class OrderReviewView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="查询订单可评状态",
        description="仅订单本人可访问；返回是否可评、不可评原因、评价窗口截止时间与已有评价。",
        responses={200: ReviewEligibilitySerializer},
    )
    def get(self, request, order_no: str):
        order, review = services.get_order_review_state(request.user, order_no)
        return Response(selectors.eligibility_payload(order, review))

    @extend_schema(
        summary="提交订单评价",
        description="仅已完成且 7 天内订单可评；一单一评，驳回后可覆盖重提并回到待审核。",
        request=ReviewSubmitSerializer,
        responses={201: ReviewEligibilitySerializer, 200: ReviewEligibilitySerializer},
    )
    def post(self, request, order_no: str):
        serializer = ReviewSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review, created = services.submit_review(request.user, order_no, serializer.validated_data)
        order, review = services.get_order_review_state(request.user, order_no)
        payload = selectors.eligibility_payload(order, review)
        return Response(
            payload,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ReviewImageUploadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="上传评价图片",
        description="仅评价本人；白名单 jpg/jpeg/png/webp，单张不超过 5MB，最多 3 张。",
        request=ReviewImageUploadSerializer,
        responses={201: ReviewImageSerializer},
    )
    def post(self, request, public_id: str):
        serializer = ReviewImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = services.add_review_image(
            request.user, public_id, serializer.validated_data["file"]
        )
        return Response(selectors.review_image_payload(image), status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# 后台
# ---------------------------------------------------------------------------
class AdminReviewListView(generics.GenericAPIView):
    permission_classes = [CanManageReviews]
    serializer_class = AdminReviewSerializer
    queryset = Review.objects.none()

    @extend_schema(
        summary="后台评价审核列表",
        description="运营按状态、星级与关键词筛选评价，含订单号、商品、用户与图片。",
        parameters=ADMIN_REVIEW_PARAMS,
        responses={200: AdminReviewSerializer(many=True)},
    )
    def get(self, request):
        queryset = selectors.admin_review_queryset(request.query_params)
        page = self.paginate_queryset(queryset)
        data = [selectors.admin_review_payload(review) for review in page]
        return self.get_paginated_response(data)


class AdminReviewApproveView(APIView):
    permission_classes = [CanManageReviews]

    @extend_schema(
        summary="审核通过评价",
        description="仅待审核评价可通过；通过后前台展示并刷新商品评分聚合。",
        request=None,
        responses={200: AdminReviewSerializer},
    )
    def post(self, request, public_id: str):
        review = services.approve_review(request.user, public_id)
        return Response(selectors.admin_review_payload(review))


class AdminReviewRejectView(APIView):
    permission_classes = [CanManageReviews]

    @extend_schema(
        summary="审核驳回评价",
        description="仅待审核评价可驳回，必须填写原因；驳回后用户可覆盖重提。",
        request=ReviewRejectSerializer,
        responses={200: AdminReviewSerializer},
    )
    def post(self, request, public_id: str):
        serializer = ReviewRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = services.reject_review(
            request.user, public_id, serializer.validated_data["reject_reason"]
        )
        return Response(selectors.admin_review_payload(review))
