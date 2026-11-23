"""订单路由，统一挂载在 /api/v1/。"""

from django.urls import path

from apps.coupons import api as coupon_api
from apps.orders import api

app_name = "orders"

urlpatterns = [
    path("orders/preview/", api.OrderPreviewView.as_view(), name="preview"),
    path("users/me/orders/summary/", api.OrderSummaryView.as_view(), name="summary"),
    path("orders/", api.OrderListCreateView.as_view(), name="list-create"),
    path("orders/<str:order_no>/", api.OrderDetailView.as_view(), name="detail"),
    path(
        "orders/<str:order_no>/coupons/",
        coupon_api.OrderCouponTrialView.as_view(),
        name="coupons",
    ),
    path("orders/<str:order_no>/cancel/", api.OrderCancelView.as_view(), name="cancel"),
    path("orders/<str:order_no>/confirm/", api.OrderConfirmView.as_view(), name="confirm"),
    path("admin/orders/", api.AdminOrderListView.as_view(), name="admin-list"),
    path(
        "admin/orders/<str:order_no>/ship/",
        api.AdminOrderShipView.as_view(),
        name="admin-ship",
    ),
]
