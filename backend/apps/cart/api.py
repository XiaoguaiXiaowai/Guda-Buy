"""购物车 HTTP 适配层：仅做协议转换，业务规则在 services。"""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart import selectors, services
from apps.cart.serializers import (
    AddCartItemSerializer,
    CartClearResultSerializer,
    CartCountSerializer,
    CartItemSerializer,
    CartSerializer,
    ClearCartSerializer,
    UpdateCartItemSerializer,
)


class CartDetailView(APIView):
    @extend_schema(
        summary="购物车明细",
        description="返回当前用户购物车项、失效/库存不足标记与可结算金额（金额为字符串）。",
        responses={200: CartSerializer},
    )
    def get(self, request):
        return Response(selectors.cart_payload(request.user))


class CartItemCreateView(APIView):
    @extend_schema(
        summary="加入购物车",
        description="同一 SKU 合并数量；校验上架状态、库存、单项 99 件与最多 50 种商品。",
        request=AddCartItemSerializer,
        responses={201: CartItemSerializer},
    )
    def post(self, request):
        serializer = AddCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = services.add_item(
            request.user,
            serializer.validated_data["sku_public_id"],
            serializer.validated_data["quantity"],
        )
        return Response(
            CartItemSerializer(selectors.item_payload(item)).data,
            status=status.HTTP_201_CREATED,
        )


class CartItemDetailView(APIView):
    @extend_schema(
        summary="修改购物车项",
        description="可改数量或勾选状态；数量为 0 视为删除并返回 204。",
        request=UpdateCartItemSerializer,
        responses={
            200: CartItemSerializer,
            204: OpenApiResponse(description="已删除"),
        },
    )
    def patch(self, request, public_id: str):
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = services.update_item(
            request.user,
            public_id,
            quantity=serializer.validated_data.get("quantity"),
            is_selected=serializer.validated_data.get("is_selected"),
        )
        if item is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(CartItemSerializer(selectors.item_payload(item)).data)

    @extend_schema(summary="删除购物车项", responses={204: OpenApiResponse(description="已删除")})
    def delete(self, request, public_id: str):
        services.delete_item(request.user, public_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartClearView(APIView):
    @extend_schema(
        summary="清空购物车",
        description="默认清空全部；only_selected=true 时只清空已勾选项。",
        request=ClearCartSerializer,
        responses={200: CartClearResultSerializer},
    )
    def post(self, request):
        serializer = ClearCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deleted = services.clear_cart(
            request.user, only_selected=serializer.validated_data["only_selected"]
        )
        return Response({"deleted": deleted})


class CartCountView(APIView):
    @extend_schema(
        summary="购物车角标",
        description="返回购物车商品种数与总件数，用于顶部角标。",
        responses={200: CartCountSerializer},
    )
    def get(self, request):
        return Response(selectors.cart_count(request.user))
