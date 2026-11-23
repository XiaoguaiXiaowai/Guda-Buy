"""评价路由，统一挂载在 /api/v1/。"""

from django.urls import path

from apps.reviews import api

app_name = "reviews"

urlpatterns = [
    path(
        "products/<str:public_id>/reviews/",
        api.ProductReviewListView.as_view(),
        name="product-reviews",
    ),
    path("orders/<str:order_no>/review/", api.OrderReviewView.as_view(), name="order-review"),
    path(
        "reviews/<str:public_id>/images/",
        api.ReviewImageUploadView.as_view(),
        name="review-images",
    ),
    path("admin/reviews/", api.AdminReviewListView.as_view(), name="admin-list"),
    path(
        "admin/reviews/<str:public_id>/approve/",
        api.AdminReviewApproveView.as_view(),
        name="admin-approve",
    ),
    path(
        "admin/reviews/<str:public_id>/reject/",
        api.AdminReviewRejectView.as_view(),
        name="admin-reject",
    ),
]
