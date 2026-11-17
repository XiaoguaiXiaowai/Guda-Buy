"""CMS HTTP 适配层：前台内容接口与后台内容管理接口。"""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cms import selectors, services
from apps.cms.models import CmsPage
from apps.cms.permissions import CanPublishPage, IsCmsStaff
from apps.cms.serializers import (
    AdminAnnouncementSerializer,
    AdminBannerSerializer,
    AdminPageSerializer,
    AdminSectionSerializer,
    AnnouncementWriteSerializer,
    BannerImageUploadSerializer,
    BannerWriteSerializer,
    CmsAnnouncementPublicSerializer,
    CmsBannerPublicSerializer,
    CmsHomeSerializer,
    CmsPagePublicSerializer,
    PageStatusSerializer,
    PageWriteSerializer,
    SectionWriteSerializer,
)


# ---------------------------------------------------------------------------
# 前台
# ---------------------------------------------------------------------------
class CmsPageView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="CMS 页面",
        description="仅返回已发布页面；草稿、下线或不存在均返回 404 CMS_PAGE_NOT_FOUND。",
        responses={200: CmsPagePublicSerializer},
    )
    def get(self, request, slug: str):  # noqa: ARG002
        return Response(selectors.get_page(slug))


class CmsBannerListView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="轮播位",
        description="仅返回启用且处于展示时间窗内的轮播，按权重倒序。",
        parameters=[OpenApiParameter("position", str, description="HOME_TOP / HOME_MIDDLE")],
        responses={200: CmsBannerPublicSerializer(many=True)},
    )
    def get(self, request):
        return Response(selectors.list_banners(request.query_params.get("position") or None))


class CmsAnnouncementListView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="公告列表",
        description="仅返回启用公告，按发布时间倒序，可按 limit 截断。",
        parameters=[OpenApiParameter("limit", int, description="返回条数上限")],
        responses={200: CmsAnnouncementPublicSerializer(many=True)},
    )
    def get(self, request):
        raw_limit = request.query_params.get("limit")
        limit = min(int(raw_limit), 20) if raw_limit and raw_limit.isdigit() else None
        return Response(selectors.list_announcements(limit=limit))


class CmsHomeView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="首页聚合",
        description="聚合首页轮播、公告与推荐商品，缓存 5 分钟，任一区块失败不影响其他区块。",
        responses={200: CmsHomeSerializer},
    )
    def get(self, request):  # noqa: ARG002
        return Response(selectors.home_aggregate())


# ---------------------------------------------------------------------------
# 后台：栏目
# ---------------------------------------------------------------------------
class AdminCmsSectionListCreateView(APIView):
    permission_classes = [IsCmsStaff]

    @extend_schema(summary="后台栏目列表", responses=AdminSectionSerializer(many=True))
    def get(self, request):  # noqa: ARG002
        return Response(AdminSectionSerializer(selectors.admin_section_queryset(), many=True).data)

    @extend_schema(
        summary="新建栏目",
        request=SectionWriteSerializer,
        responses={201: AdminSectionSerializer},
    )
    def post(self, request):
        serializer = SectionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        section = services.create_section(serializer.validated_data, operator=request.user)
        section.page_count = 0
        return Response(AdminSectionSerializer(section).data, status=status.HTTP_201_CREATED)


class AdminCmsSectionDetailView(APIView):
    permission_classes = [IsCmsStaff]

    @extend_schema(
        summary="更新栏目", request=SectionWriteSerializer, responses=AdminSectionSerializer
    )
    def put(self, request, public_id: str):
        serializer = SectionWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.update_section(public_id, serializer.validated_data, operator=request.user)
        section = selectors.get_admin_section(public_id)
        return Response(AdminSectionSerializer(section).data)

    @extend_schema(summary="删除栏目", responses={204: OpenApiResponse(description="已删除")})
    def delete(self, request, public_id: str):
        services.delete_section(public_id, operator=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# 后台：页面
# ---------------------------------------------------------------------------
ADMIN_PAGE_PARAMS = [
    OpenApiParameter("status", str, description="DRAFT / PUBLISHED / OFFLINE"),
    OpenApiParameter("section", str, description="栏目 public_id"),
    OpenApiParameter("search", str, description="标题或 slug 关键词"),
    OpenApiParameter("page", int, description="页码，从 1 开始"),
    OpenApiParameter("page_size", int, description="每页条数，最大 100"),
]


class AdminCmsPageListCreateView(generics.GenericAPIView):
    permission_classes = [IsCmsStaff]
    serializer_class = AdminPageSerializer
    queryset = CmsPage.objects.none()

    @extend_schema(
        summary="后台页面列表",
        parameters=ADMIN_PAGE_PARAMS,
        responses=AdminPageSerializer(many=True),
    )
    def get(self, request):
        queryset = selectors.admin_page_queryset(request.query_params)
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @extend_schema(
        summary="新建页面",
        description="新建页面固定为草稿状态，正文经服务端白名单清洗后入库。",
        request=PageWriteSerializer,
        responses={201: AdminPageSerializer},
    )
    def post(self, request):
        serializer = PageWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        page = services.create_page(serializer.validated_data, operator=request.user)
        page = selectors.get_admin_page(page.public_id)
        return Response(AdminPageSerializer(page).data, status=status.HTTP_201_CREATED)


class AdminCmsPageDetailView(APIView):
    permission_classes = [IsCmsStaff]

    @extend_schema(summary="后台页面详情", responses=AdminPageSerializer)
    def get(self, request, public_id: str):  # noqa: ARG002
        return Response(AdminPageSerializer(selectors.get_admin_page(public_id)).data)

    @extend_schema(summary="更新页面", request=PageWriteSerializer, responses=AdminPageSerializer)
    def put(self, request, public_id: str):
        serializer = PageWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.update_page(public_id, serializer.validated_data, operator=request.user)
        return Response(AdminPageSerializer(selectors.get_admin_page(public_id)).data)

    @extend_schema(summary="删除页面", responses={204: OpenApiResponse(description="已删除")})
    def delete(self, request, public_id: str):
        services.delete_page(public_id, operator=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminCmsPageStatusView(APIView):
    permission_classes = [IsCmsStaff, CanPublishPage]

    @extend_schema(
        summary="发布或下线页面",
        description="action=PUBLISH 发布，action=OFFLINE 下线；非法状态流转返回 409。",
        request=PageStatusSerializer,
        responses=AdminPageSerializer,
    )
    def post(self, request, public_id: str):
        serializer = PageStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.change_page_status(
            public_id, serializer.validated_data["action"], operator=request.user
        )
        return Response(AdminPageSerializer(selectors.get_admin_page(public_id)).data)


# ---------------------------------------------------------------------------
# 后台：轮播位
# ---------------------------------------------------------------------------
class AdminCmsBannerListCreateView(APIView):
    permission_classes = [IsCmsStaff]

    @extend_schema(
        summary="后台轮播列表",
        parameters=[
            OpenApiParameter("position", str, description="HOME_TOP / HOME_MIDDLE"),
            OpenApiParameter("status", str, description="ENABLED / DISABLED"),
        ],
        responses=AdminBannerSerializer(many=True),
    )
    def get(self, request):
        return Response(
            AdminBannerSerializer(
                selectors.admin_banner_queryset(request.query_params), many=True
            ).data
        )

    @extend_schema(
        summary="新建轮播", request=BannerWriteSerializer, responses={201: AdminBannerSerializer}
    )
    def post(self, request):
        serializer = BannerWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        banner = services.create_banner(serializer.validated_data, operator=request.user)
        return Response(AdminBannerSerializer(banner).data, status=status.HTTP_201_CREATED)


class AdminCmsBannerDetailView(APIView):
    permission_classes = [IsCmsStaff]

    @extend_schema(summary="后台轮播详情", responses=AdminBannerSerializer)
    def get(self, request, public_id: str):  # noqa: ARG002
        return Response(AdminBannerSerializer(services.get_banner(public_id)).data)

    @extend_schema(
        summary="更新轮播", request=BannerWriteSerializer, responses=AdminBannerSerializer
    )
    def put(self, request, public_id: str):
        serializer = BannerWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        banner = services.update_banner(public_id, serializer.validated_data, operator=request.user)
        return Response(AdminBannerSerializer(banner).data)

    @extend_schema(summary="删除轮播", responses={204: OpenApiResponse(description="已删除")})
    def delete(self, request, public_id: str):
        services.delete_banner(public_id, operator=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminCmsBannerImageView(APIView):
    permission_classes = [IsCmsStaff]

    @extend_schema(
        summary="上传轮播图",
        description="白名单 jpg/jpeg/png/webp，最大 5MB，尺寸不超过 4096px；上传后替换旧图。",
        request=BannerImageUploadSerializer,
        responses=AdminBannerSerializer,
    )
    def post(self, request, public_id: str):
        serializer = BannerImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        banner = services.save_banner_image(
            public_id, serializer.validated_data["file"], operator=request.user
        )
        return Response(AdminBannerSerializer(banner).data)


# ---------------------------------------------------------------------------
# 后台：公告
# ---------------------------------------------------------------------------
class AdminCmsAnnouncementListCreateView(APIView):
    permission_classes = [IsCmsStaff]

    @extend_schema(
        summary="后台公告列表",
        parameters=[
            OpenApiParameter("status", str, description="ENABLED / DISABLED"),
            OpenApiParameter("level", str, description="NORMAL / IMPORTANT"),
        ],
        responses=AdminAnnouncementSerializer(many=True),
    )
    def get(self, request):
        return Response(
            AdminAnnouncementSerializer(
                selectors.admin_announcement_queryset(request.query_params), many=True
            ).data
        )

    @extend_schema(
        summary="新建公告",
        request=AnnouncementWriteSerializer,
        responses={201: AdminAnnouncementSerializer},
    )
    def post(self, request):
        serializer = AnnouncementWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        announcement = services.create_announcement(
            serializer.validated_data, operator=request.user
        )
        return Response(
            AdminAnnouncementSerializer(announcement).data, status=status.HTTP_201_CREATED
        )


class AdminCmsAnnouncementDetailView(APIView):
    permission_classes = [IsCmsStaff]

    @extend_schema(
        summary="更新公告",
        request=AnnouncementWriteSerializer,
        responses=AdminAnnouncementSerializer,
    )
    def put(self, request, public_id: str):
        serializer = AnnouncementWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        announcement = services.update_announcement(
            public_id, serializer.validated_data, operator=request.user
        )
        return Response(AdminAnnouncementSerializer(announcement).data)

    @extend_schema(summary="删除公告", responses={204: OpenApiResponse(description="已删除")})
    def delete(self, request, public_id: str):
        services.delete_announcement(public_id, operator=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
