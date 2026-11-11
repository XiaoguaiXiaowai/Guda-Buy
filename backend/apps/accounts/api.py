"""账号 HTTP 适配层：认证、令牌、个人资料与地址。"""

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import selectors, services
from apps.accounts.serializers import (
    AddressSerializer,
    AvatarUploadSerializer,
    EmailCodeRequestSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserProfileSerializer,
)
from apps.accounts.throttles import EmailCodeIPThrottle, LoginAccountThrottle, RegisterIPThrottle
from apps.common.exceptions import BusinessError


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.JWT_REFRESH_DAYS * 24 * 3600,
        httponly=True,
        secure=settings.AUTH_REFRESH_COOKIE_SECURE,
        samesite="Lax",
        path=settings.AUTH_REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        path=settings.AUTH_REFRESH_COOKIE_PATH,
    )


def _refresh_from_request(request) -> str:
    token = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME, "")
    if not token and isinstance(request.data, dict):
        token = request.data.get("refresh", "")
    if not token:
        raise BusinessError("AUTH_REFRESH_REVOKED", "登录状态已失效，请重新登录", http_status=401)
    return token


def _verify_cookie_origin(request) -> None:
    """Cookie 接口的 CSRF 兜底：校验自定义头与 Origin 白名单（架构文档 3.7）。"""
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        raise BusinessError("COMMON_PERMISSION_DENIED", "非法请求来源", http_status=403)
    origin = request.headers.get("Origin")
    if not origin:
        return
    allowed = {settings.APP_SITE_URL.rstrip("/")}
    allowed.update(getattr(settings, "CORS_ALLOWED_ORIGINS", []))
    if origin.rstrip("/") not in allowed:
        raise BusinessError("COMMON_PERMISSION_DENIED", "非法请求来源", http_status=403)


def _auth_payload(user, access: str, request=None) -> dict:
    return {
        "access": access,
        "expires_in": settings.JWT_ACCESS_MINUTES * 60,
        "user": UserProfileSerializer(user, context={"request": request}).data,
    }


class EmailCodeView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [EmailCodeIPThrottle]

    @extend_schema(
        summary="发送邮箱验证码",
        description="向注册邮箱发送 6 位验证码，5 分钟有效；同一邮箱 60 秒内不可重发。",
        request=EmailCodeRequestSerializer,
        responses={200: OpenApiResponse(description="验证码已发送")},
    )
    def post(self, request):
        serializer = EmailCodeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.send_email_code(serializer.validated_data["email"])
        return Response({"message": "验证码已发送，请注意查收"})


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [RegisterIPThrottle]

    @extend_schema(
        summary="注册会员",
        description="邮箱 + 用户名 + 密码 + 邮箱验证码注册，成功后直接登录。",
        request=RegisterSerializer,
        responses={201: OpenApiResponse(description="注册成功，返回 access 并下发 refresh Cookie")},
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.register_user(**serializer.validated_data)
        access, refresh = services.issue_tokens(user)
        response = Response(_auth_payload(user, access, request), status=status.HTTP_201_CREATED)
        _set_refresh_cookie(response, refresh)
        return response


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginAccountThrottle]

    @extend_schema(
        summary="账号登录",
        description="用户名或邮箱 + 密码登录；连续失败 5 次锁定 15 分钟。",
        request=LoginSerializer,
        responses={200: OpenApiResponse(description="登录成功，返回 access 并下发 refresh Cookie")},
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.authenticate_account(
            serializer.validated_data["account"], serializer.validated_data["password"]
        )
        access, refresh = services.issue_tokens(user)
        response = Response(_auth_payload(user, access, request))
        _set_refresh_cookie(response, refresh)
        return response


class RefreshView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="刷新访问令牌",
        description="从 HttpOnly Cookie 读取 refresh，轮换后返回新的 access 并更新 Cookie。",
        request=None,
        responses={200: OpenApiResponse(description="返回新的 access")},
    )
    def post(self, request):
        _verify_cookie_origin(request)
        raw_refresh = _refresh_from_request(request)
        access, refresh = services.rotate_refresh_token(raw_refresh)
        response = Response({"access": access, "expires_in": settings.JWT_ACCESS_MINUTES * 60})
        _set_refresh_cookie(response, refresh)
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="退出登录",
        description="将 refresh 加入黑名单并清除 Cookie。",
        request=None,
        responses={200: OpenApiResponse(description="已退出登录")},
    )
    def post(self, request):
        _verify_cookie_origin(request)
        raw_refresh = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME, "")
        if raw_refresh:
            services.blacklist_refresh_token(raw_refresh)
        response = Response({"message": "已退出登录"})
        _clear_refresh_cookie(response)
        return response


class PasswordResetRequestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="请求找回密码",
        description="向已注册邮箱发送一次性重置链接（30 分钟有效）；无论邮箱是否存在均返回成功。",
        request=PasswordResetRequestSerializer,
        responses={200: OpenApiResponse(description="请求已受理")},
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_password_reset(serializer.validated_data["email"])
        return Response({"message": "如果该邮箱已注册，重置邮件将很快送达"})


class PasswordResetConfirmView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="确认重置密码",
        description="校验一次性 token 并设置新密码，成功后所有 refresh 失效。",
        request=PasswordResetConfirmSerializer,
        responses={200: OpenApiResponse(description="密码已重置")},
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.confirm_password_reset(
            serializer.validated_data["token"], serializer.validated_data["new_password"]
        )
        return Response({"message": "密码已重置，请使用新密码登录"})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="查询个人信息",
        responses=UserProfileSerializer,
    )
    def get(self, request):
        return Response(UserProfileSerializer(request.user, context={"request": request}).data)

    @extend_schema(
        summary="更新个人信息",
        request=ProfileUpdateSerializer,
        responses=UserProfileSerializer,
    )
    def patch(self, request):
        serializer = ProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = services.update_profile(request.user, serializer.validated_data)
        return Response(UserProfileSerializer(user, context={"request": request}).data)


class AvatarUploadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="上传头像",
        description="白名单 jpg/jpeg/png/webp，最大 5MB，尺寸不超过 4096px。",
        request=AvatarUploadSerializer,
        responses=UserProfileSerializer,
    )
    def post(self, request):
        serializer = AvatarUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        services.save_avatar(user, serializer.validated_data["file"])
        user.refresh_from_db()
        return Response(UserProfileSerializer(user, context={"request": request}).data)


class AddressListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="地址列表",
        responses=AddressSerializer(many=True),
    )
    def get(self, request):
        addresses = services.list_addresses(request.user)
        return Response(AddressSerializer(addresses, many=True).data)

    @extend_schema(
        summary="新增地址",
        description="每个用户最多 20 条；首条地址自动设为默认。",
        request=AddressSerializer,
        responses={201: AddressSerializer},
    )
    def post(self, request):
        serializer = AddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        address = services.create_address(request.user, serializer.validated_data)
        return Response(AddressSerializer(address).data, status=status.HTTP_201_CREATED)


class AddressDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="地址详情", responses=AddressSerializer)
    def get(self, request, public_id: str):
        address = selectors.get_user_address(request.user, public_id)
        _ensure_address(address)
        return Response(AddressSerializer(address).data)

    @extend_schema(
        summary="全量更新地址",
        request=AddressSerializer,
        responses=AddressSerializer,
    )
    def put(self, request, public_id: str):
        serializer = AddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        address = services.update_address(request.user, public_id, serializer.validated_data)
        return Response(AddressSerializer(address).data)

    @extend_schema(summary="删除地址", responses={204: OpenApiResponse(description="已删除")})
    def delete(self, request, public_id: str):
        services.delete_address(request.user, public_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AddressDefaultView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="设为默认地址",
        description="同一用户默认地址唯一，旧的自动取消默认。",
        request=None,
        responses=AddressSerializer,
    )
    def post(self, request, public_id: str):
        address = services.set_default_address(request.user, public_id)
        return Response(AddressSerializer(address).data)


def _ensure_address(address) -> None:
    if address is None:
        raise BusinessError("COMMON_NOT_FOUND", "地址不存在", http_status=404)
