"""商品模块路由，统一挂载在 /api/v1/。"""

from django.urls import path

from apps.catalog import api

app_name = "catalog"

urlpatterns = [
    # 前台
    path("categories/tree/", api.CategoryTreeView.as_view(), name="category-tree"),
    path("products/", api.ProductListView.as_view(), name="product-list"),
    path("products/suggest/", api.ProductSuggestView.as_view(), name="product-suggest"),
    path("products/<str:public_id>/", api.ProductDetailView.as_view(), name="product-detail"),
    path(
        "products/<str:public_id>/related/",
        api.RelatedProductsView.as_view(),
        name="product-related",
    ),
    # 后台：分类
    path(
        "admin/categories/",
        api.AdminCategoryListCreateView.as_view(),
        name="admin-category-list",
    ),
    path(
        "admin/categories/<str:public_id>/",
        api.AdminCategoryDetailView.as_view(),
        name="admin-category-detail",
    ),
    # 后台：商品
    path(
        "admin/products/",
        api.AdminProductListCreateView.as_view(),
        name="admin-product-list",
    ),
    path(
        "admin/products/<str:public_id>/",
        api.AdminProductDetailView.as_view(),
        name="admin-product-detail",
    ),
    path(
        "admin/products/<str:public_id>/publish/",
        api.AdminProductPublishView.as_view(),
        name="admin-product-publish",
    ),
    path(
        "admin/products/<str:public_id>/unpublish/",
        api.AdminProductUnpublishView.as_view(),
        name="admin-product-unpublish",
    ),
    path(
        "admin/products/<str:public_id>/skus/",
        api.AdminSkuListCreateView.as_view(),
        name="admin-sku-list",
    ),
    path(
        "admin/products/<str:public_id>/images/",
        api.AdminProductImageUploadView.as_view(),
        name="admin-product-image-upload",
    ),
    path(
        "admin/products/<str:public_id>/images/<str:image_public_id>/",
        api.AdminProductImageDeleteView.as_view(),
        name="admin-product-image-delete",
    ),
    path("admin/skus/<str:public_id>/", api.AdminSkuDetailView.as_view(), name="admin-sku-detail"),
    path(
        "admin/skus/<str:public_id>/stock/",
        api.AdminSkuStockView.as_view(),
        name="admin-sku-stock",
    ),
]
