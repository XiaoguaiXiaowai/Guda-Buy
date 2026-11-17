"""购物车路由，统一挂载在 /api/v1/。"""

from django.urls import path

from apps.cart import api

app_name = "cart"

urlpatterns = [
    path("cart/", api.CartDetailView.as_view(), name="detail"),
    path("cart/items/", api.CartItemCreateView.as_view(), name="item-create"),
    path("cart/items/<str:public_id>/", api.CartItemDetailView.as_view(), name="item-detail"),
    path("cart/clear/", api.CartClearView.as_view(), name="clear"),
    path("cart/count/", api.CartCountView.as_view(), name="count"),
]
