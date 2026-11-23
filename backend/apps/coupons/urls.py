"""优惠券路由，统一挂载在 /api/v1/。"""

from django.urls import path

from apps.coupons import api

app_name = "coupons"

urlpatterns = [
    path("coupons/available/", api.AvailableCouponListView.as_view(), name="available"),
    path("coupons/<str:public_id>/claim/", api.CouponClaimView.as_view(), name="claim"),
    path("users/me/coupons/", api.MyCouponsView.as_view(), name="my-coupons"),
    path("admin/coupons/", api.AdminCouponListCreateView.as_view(), name="admin-list"),
    path(
        "admin/coupons/<str:public_id>/",
        api.AdminCouponDetailView.as_view(),
        name="admin-detail",
    ),
]
