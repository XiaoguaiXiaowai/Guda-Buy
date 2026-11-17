"""支付路由，统一挂载在 /api/v1/。"""

from django.urls import path

from apps.payments import api

app_name = "payments"

urlpatterns = [
    path("payments/callback/", api.PaymentCallbackView.as_view(), name="callback"),
    path(
        "payments/<str:order_no>/mock-pay/",
        api.PaymentMockPayView.as_view(),
        name="mock-pay",
    ),
    path("payments/<str:payment_no>/", api.PaymentDetailView.as_view(), name="detail"),
    path("admin/payments/", api.AdminPaymentListView.as_view(), name="admin-list"),
]
