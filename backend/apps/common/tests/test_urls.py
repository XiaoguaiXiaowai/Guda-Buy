"""仅用于异常契约测试的临时路由。"""

from django.urls import path
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import BusinessError


class _Base(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []


class ValidationErrorView(_Base):
    def get(self, request):  # noqa: ARG002
        raise ValidationError({"email": ["邮箱格式不正确"]})


class AuthenticationErrorView(_Base):
    def get(self, request):  # noqa: ARG002
        raise AuthenticationFailed()


class PermissionErrorView(_Base):
    def get(self, request):  # noqa: ARG002
        raise PermissionDenied()


class NotFoundErrorView(_Base):
    def get(self, request):  # noqa: ARG002
        raise NotFound()


class InternalErrorView(_Base):
    def get(self, request):  # noqa: ARG002
        raise RuntimeError("数据库连接串泄露示例")


class BusinessErrorView(_Base):
    def get(self, request):  # noqa: ARG002
        raise BusinessError(
            "CART_STOCK_NOT_ENOUGH", "库存不足", http_status=422, detail={"available": 2}
        )


class PlainSuccessView(_Base):
    def get(self, request):  # noqa: ARG002
        return Response({"ok": True})


urlpatterns = [
    path("exc/400/", ValidationErrorView.as_view()),
    path("exc/401/", AuthenticationErrorView.as_view()),
    path("exc/403/", PermissionErrorView.as_view()),
    path("exc/404/", NotFoundErrorView.as_view()),
    path("exc/500/", InternalErrorView.as_view()),
    path("exc/business/", BusinessErrorView.as_view()),
    path("ok/", PlainSuccessView.as_view()),
]
