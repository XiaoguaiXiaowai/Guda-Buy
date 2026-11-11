"""账号模块路由，统一挂载在 /api/v1/。"""

from django.urls import path

from apps.accounts import api

app_name = "accounts"

urlpatterns = [
    path("auth/email-code/", api.EmailCodeView.as_view(), name="email-code"),
    path("auth/register/", api.RegisterView.as_view(), name="register"),
    path("auth/login/", api.LoginView.as_view(), name="login"),
    path("auth/refresh/", api.RefreshView.as_view(), name="refresh"),
    path("auth/logout/", api.LogoutView.as_view(), name="logout"),
    path("auth/password/reset/", api.PasswordResetRequestView.as_view(), name="password-reset"),
    path(
        "auth/password/reset/confirm/",
        api.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("users/me/", api.MeView.as_view(), name="me"),
    path("users/me/avatar/", api.AvatarUploadView.as_view(), name="avatar"),
    path("users/me/addresses/", api.AddressListCreateView.as_view(), name="address-list"),
    path(
        "users/me/addresses/<str:public_id>/",
        api.AddressDetailView.as_view(),
        name="address-detail",
    ),
    path(
        "users/me/addresses/<str:public_id>/default/",
        api.AddressDefaultView.as_view(),
        name="address-default",
    ),
]
