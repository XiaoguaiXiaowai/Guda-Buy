"""商品 HTTP 适配层：前台浏览接口与后台商品管理接口。"""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog import selectors, services
from apps.catalog.models import Product
from apps.catalog.permissions import CanChangeStock, IsCatalogStaff
from apps.catalog.serializers import (
    AdminCategorySerializer,
    AdminProductSerializer,
    AdminSkuSerializer,
    CategoryTreeItemSerializer,
    CategoryWriteSerializer,
    ProductDetailSerializer,
    ProductImageSerializer,
    ProductImageUploadSerializer,
    ProductListItemSerializer,
    ProductSuggestSerializer,
    ProductWriteSerializer,
    SkuWriteSerializer,
    StockAdjustSerializer,
)
from apps.common.exceptions import BusinessError

PUBLIC_PRODUCT_PARAMS = [
    OpenApiParameter("category", str, description="分类 public_id；一级分类自动包含二级"),
    OpenApiParameter("price_min", str, description="最低价下限"),
    OpenApiParameter("price_max", str, description="最高价上限"),
    OpenApiParameter("search", str, description="商品名称关键词（最多 30 字）"),
    OpenApiParameter("ordering", str, description="price / -price / sales / -sales / created_at"),
    OpenApiParameter("page", int, description="页码，从 1 开始"),
    OpenApiParameter("page_size", int, description="每页条数，最大 100"),
]


# ---------------------------------------------------------------------------
# 前台
# ---------------------------------------------------------------------------
class CategoryTreeView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="分类树",
        description="返回两级分类树与各分类在售商品数，结果按版本号缓存 1 小时。",
        responses={200: CategoryTreeItemSerializer(many=True)},
    )
    def get(self, request):  # noqa: ARG002
        return Response(selectors.category_tree())


class ProductListView(generics.GenericAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = ProductListItemSerializer
    queryset = Product.objects.none()

    @extend_schema(
        summary="商品列表",
        description="仅返回在售商品；支持分类、价格区间、关键词与白名单排序。",
        parameters=PUBLIC_PRODUCT_PARAMS,
        responses={200: ProductListItemSerializer(many=True)},
    )
    def get(self, request):
        queryset = selectors.list_products(request.query_params)
        page = self.paginate_queryset(queryset)
        items = [selectors.product_list_item(product) for product in page]
        return self.get_paginated_response(items)


class ProductDetailView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="商品详情",
        description="返回在售 SKU、图集与库存状态；下架或不存在均返回 404 PRODUCT_NOT_FOUND。",
        responses={200: ProductDetailSerializer},
    )
    def get(self, request, public_id: str):  # noqa: ARG002
        payload = selectors.get_product_detail(public_id)
        if payload is None:
            raise BusinessError("PRODUCT_NOT_FOUND", "商品不存在或已下架", http_status=404)
        return Response(payload)


class RelatedProductsView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="相关推荐",
        description="同分类在售热销商品，最多 8 条。",
        responses={200: ProductListItemSerializer(many=True)},
    )
    def get(self, request, public_id: str):  # noqa: ARG002
        return Response(selectors.list_related(public_id))


class ProductSuggestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="搜索联想",
        description="按商品名前缀优先匹配，最多 10 条。",
        parameters=[OpenApiParameter("keyword", str, required=True)],
        responses={200: ProductSuggestSerializer(many=True)},
    )
    def get(self, request):
        return Response(selectors.suggest(request.query_params.get("keyword") or ""))


# ---------------------------------------------------------------------------
# 后台：分类
# ---------------------------------------------------------------------------
class AdminCategoryListCreateView(APIView):
    permission_classes = [IsCatalogStaff]

    @extend_schema(summary="后台分类列表", responses=AdminCategorySerializer(many=True))
    def get(self, request):  # noqa: ARG002
        return Response(AdminCategorySerializer(selectors.admin_category_list(), many=True).data)

    @extend_schema(
        summary="新建分类",
        request=CategoryWriteSerializer,
        responses={201: AdminCategorySerializer},
    )
    def post(self, request):
        serializer = CategoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = services.create_category(**serializer.validated_data)
        category.product_count = 0
        return Response(AdminCategorySerializer(category).data, status=status.HTTP_201_CREATED)


class AdminCategoryDetailView(APIView):
    permission_classes = [IsCatalogStaff]

    @extend_schema(
        summary="更新分类",
        request=CategoryWriteSerializer,
        responses=AdminCategorySerializer,
    )
    def put(self, request, public_id: str):
        serializer = CategoryWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data.pop("parent_public_id", None)
        category = services.update_category(public_id, data)
        category.product_count = category.products.filter(is_deleted=False).count()
        return Response(AdminCategorySerializer(category).data)

    @extend_schema(summary="删除分类", responses={204: OpenApiResponse(description="已删除")})
    def delete(self, request, public_id: str):  # noqa: ARG002
        services.delete_category(public_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# 后台：商品
# ---------------------------------------------------------------------------
class AdminProductListCreateView(generics.GenericAPIView):
    permission_classes = [IsCatalogStaff]
    serializer_class = AdminProductSerializer
    queryset = Product.objects.none()

    @extend_schema(
        summary="后台商品列表",
        parameters=PUBLIC_PRODUCT_PARAMS[:4],
        responses=AdminProductSerializer(many=True),
    )
    def get(self, request):
        queryset = selectors.admin_product_queryset(request.query_params).prefetch_related("images")
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @extend_schema(
        summary="新建商品",
        description="新建商品为草稿状态，至少创建一个在售 SKU 后才能上架。",
        request=ProductWriteSerializer,
        responses={201: AdminProductSerializer},
    )
    def post(self, request):
        serializer = ProductWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = services.create_product(serializer.validated_data, operator=request.user)
        return Response(
            AdminProductSerializer(product, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class AdminProductDetailView(APIView):
    permission_classes = [IsCatalogStaff]

    @extend_schema(summary="后台商品详情", responses=AdminProductSerializer)
    def get(self, request, public_id: str):
        product = selectors.get_admin_product(public_id)
        return Response(AdminProductSerializer(product, context={"request": request}).data)

    @extend_schema(
        summary="更新商品", request=ProductWriteSerializer, responses=AdminProductSerializer
    )
    def put(self, request, public_id: str):
        serializer = ProductWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = services.update_product(
            public_id, serializer.validated_data, operator=request.user
        )
        product = selectors.get_admin_product(product.public_id)
        return Response(AdminProductSerializer(product, context={"request": request}).data)

    @extend_schema(
        summary="下架并软删除商品",
        responses={204: OpenApiResponse(description="已删除")},
    )
    def delete(self, request, public_id: str):  # noqa: ARG002
        services.delete_product(public_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminProductPublishView(APIView):
    permission_classes = [IsCatalogStaff]

    @extend_schema(summary="上架商品", request=None, responses=AdminProductSerializer)
    def post(self, request, public_id: str):
        services.publish_product(public_id, operator=request.user)
        product = selectors.get_admin_product(public_id)
        return Response(AdminProductSerializer(product, context={"request": request}).data)


class AdminProductUnpublishView(APIView):
    permission_classes = [IsCatalogStaff]

    @extend_schema(summary="下架商品", request=None, responses=AdminProductSerializer)
    def post(self, request, public_id: str):
        services.unpublish_product(public_id, operator=request.user)
        product = selectors.get_admin_product(public_id)
        return Response(AdminProductSerializer(product, context={"request": request}).data)


class AdminSkuListCreateView(APIView):
    permission_classes = [IsCatalogStaff]

    @extend_schema(summary="SKU 列表", responses=AdminSkuSerializer(many=True))
    def get(self, request, public_id: str):  # noqa: ARG002
        product = services.get_product(public_id)
        skus = product.skus.filter(is_deleted=False).order_by("id")
        return Response(AdminSkuSerializer(skus, many=True).data)

    @extend_schema(
        summary="新建 SKU", request=SkuWriteSerializer, responses={201: AdminSkuSerializer}
    )
    def post(self, request, public_id: str):
        product = services.get_product(public_id)
        serializer = SkuWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sku = services.create_sku(product, serializer.validated_data)
        return Response(AdminSkuSerializer(sku).data, status=status.HTTP_201_CREATED)


class AdminSkuDetailView(APIView):
    permission_classes = [IsCatalogStaff]

    @extend_schema(summary="更新 SKU", request=SkuWriteSerializer, responses=AdminSkuSerializer)
    def put(self, request, public_id: str):
        serializer = SkuWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        sku = services.update_sku(public_id, serializer.validated_data)
        return Response(AdminSkuSerializer(sku).data)


class AdminSkuStockView(APIView):
    permission_classes = [IsCatalogStaff, CanChangeStock]

    @extend_schema(
        summary="调整库存",
        description="仅支持正整数增量，调整后不得超过库存上限，每次调整写入库存流水。",
        request=StockAdjustSerializer,
        responses=AdminSkuSerializer,
    )
    def patch(self, request, public_id: str):
        serializer = StockAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sku = services.adjust_stock(
            public_id,
            serializer.validated_data["change"],
            reason=serializer.validated_data.get("reason", ""),
            operator=request.user,
        )
        return Response(AdminSkuSerializer(sku).data)


class AdminProductImageUploadView(APIView):
    permission_classes = [IsCatalogStaff]

    @extend_schema(
        summary="上传商品图",
        description="白名单 jpg/jpeg/png/webp，最大 5MB，尺寸不超过 4096px；首图自动设为主图。",
        request=ProductImageUploadSerializer,
        responses={201: ProductImageSerializer},
    )
    def post(self, request, public_id: str):
        serializer = ProductImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = services.save_product_image(public_id, serializer.validated_data["file"])
        return Response(ProductImageSerializer(image).data, status=status.HTTP_201_CREATED)


class AdminProductImageDeleteView(APIView):
    permission_classes = [IsCatalogStaff]

    @extend_schema(summary="删除商品图", responses={204: OpenApiResponse(description="已删除")})
    def delete(self, request, public_id: str, image_public_id: str):  # noqa: ARG002
        services.delete_product_image(public_id, image_public_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
