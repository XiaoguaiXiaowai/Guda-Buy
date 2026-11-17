"""CMS 模块路由，统一挂载在 /api/v1/。"""

from django.urls import path

from apps.cms import api

app_name = "cms"

urlpatterns = [
    # 前台
    path("cms/pages/<str:slug>/", api.CmsPageView.as_view(), name="page"),
    path("cms/banners/", api.CmsBannerListView.as_view(), name="banner-list"),
    path("cms/announcements/", api.CmsAnnouncementListView.as_view(), name="announcement-list"),
    path("cms/home/", api.CmsHomeView.as_view(), name="home"),
    # 后台：栏目
    path(
        "admin/cms/sections/",
        api.AdminCmsSectionListCreateView.as_view(),
        name="admin-section-list",
    ),
    path(
        "admin/cms/sections/<str:public_id>/",
        api.AdminCmsSectionDetailView.as_view(),
        name="admin-section-detail",
    ),
    # 后台：页面
    path("admin/cms/pages/", api.AdminCmsPageListCreateView.as_view(), name="admin-page-list"),
    path(
        "admin/cms/pages/<str:public_id>/",
        api.AdminCmsPageDetailView.as_view(),
        name="admin-page-detail",
    ),
    path(
        "admin/cms/pages/<str:public_id>/publish/",
        api.AdminCmsPageStatusView.as_view(),
        name="admin-page-publish",
    ),
    # 后台：轮播
    path(
        "admin/cms/banners/",
        api.AdminCmsBannerListCreateView.as_view(),
        name="admin-banner-list",
    ),
    path(
        "admin/cms/banners/<str:public_id>/",
        api.AdminCmsBannerDetailView.as_view(),
        name="admin-banner-detail",
    ),
    path(
        "admin/cms/banners/<str:public_id>/image/",
        api.AdminCmsBannerImageView.as_view(),
        name="admin-banner-image",
    ),
    # 后台：公告
    path(
        "admin/cms/announcements/",
        api.AdminCmsAnnouncementListCreateView.as_view(),
        name="admin-announcement-list",
    ),
    path(
        "admin/cms/announcements/<str:public_id>/",
        api.AdminCmsAnnouncementDetailView.as_view(),
        name="admin-announcement-detail",
    ),
]
