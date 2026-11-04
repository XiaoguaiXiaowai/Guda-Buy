"""统一异常与错误响应体（架构文档 4.3 / 4.4 / 附录 A）。"""

import logging
import uuid
from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    Throttled,
    ValidationError,
)
from rest_framework.exceptions import (
    PermissionDenied as DRFPermissionDenied,
)
from rest_framework.response import Response

from apps.common.request_id import get_request_id

logger = logging.getLogger("guda.error")


class BusinessError(Exception):
    """业务异常：携带业务码、HTTP 状态与结构化补充信息。"""

    default_code = "COMMON_INTERNAL_ERROR"
    default_status = status.HTTP_400_BAD_REQUEST
    default_message = "业务处理失败"

    def __init__(
        self,
        code: str | None = None,
        message: str | None = None,
        *,
        http_status: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.code = code or self.default_code
        self.message = message or self.default_message
        self.http_status = http_status or self.default_status
        self.detail = detail or {}
        super().__init__(self.message)


def now_iso() -> str:
    """ISO 8601 带时区的时间戳。"""
    return timezone.localtime(timezone.now()).isoformat()


def build_error_payload(
    code: str,
    message: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "detail": detail or {},
        "request_id": get_request_id() or f"req-{uuid.uuid4().hex[:8]}",
        "timestamp": now_iso(),
    }


def _status_to_code(http_status: int) -> str:
    return {
        status.HTTP_400_BAD_REQUEST: "COMMON_VALIDATION_ERROR",
        status.HTTP_401_UNAUTHORIZED: "AUTH_TOKEN_INVALID",
        status.HTTP_403_FORBIDDEN: "COMMON_PERMISSION_DENIED",
        status.HTTP_404_NOT_FOUND: "COMMON_NOT_FOUND",
        status.HTTP_405_METHOD_NOT_ALLOWED: "COMMON_METHOD_NOT_ALLOWED",
        status.HTTP_429_TOO_MANY_REQUESTS: "COMMON_RATE_LIMITED",
        status.HTTP_503_SERVICE_UNAVAILABLE: "COMMON_SERVICE_UNAVAILABLE",
    }.get(http_status, "COMMON_INTERNAL_ERROR")


def _message_of(exc: Exception, fallback: str) -> str:
    detail = getattr(exc, "detail", None)
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail and isinstance(detail[0], str):
        return detail[0]
    if isinstance(detail, dict):
        for value in detail.values():
            if isinstance(value, list) and value and isinstance(value[0], str):
                return value[0]
            if isinstance(value, str):
                return value
    return fallback


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """DRF 全局异常处理：所有错误统一为 4.3 结构，500 不暴露堆栈。"""
    if isinstance(exc, BusinessError):
        return Response(
            build_error_payload(exc.code, exc.message, exc.detail),
            status=exc.http_status,
        )

    if isinstance(exc, APIException):
        http_status = exc.status_code
        code = _status_to_code(http_status)
        message = _message_of(exc, str(exc.detail) if hasattr(exc, "detail") else "请求失败")
        detail: dict[str, Any] = {}

        if isinstance(exc, ValidationError):
            code = "COMMON_VALIDATION_ERROR"
            message = "参数校验失败"
            detail = {"fields": exc.detail}
        elif isinstance(exc, NotAuthenticated | AuthenticationFailed):
            # 未配置认证类时 DRF 会把 401 改写为 403，这里统一还原为 401
            http_status = status.HTTP_401_UNAUTHORIZED
            code = "AUTH_TOKEN_INVALID"
            message = "登录状态无效或已过期"
            detail = {}
        elif isinstance(exc, DRFPermissionDenied):
            code = "COMMON_PERMISSION_DENIED"
            message = "无权限访问该资源"
        elif isinstance(exc, NotFound):
            code = "COMMON_NOT_FOUND"
            message = "资源不存在"
        elif isinstance(exc, Throttled):
            code = "COMMON_RATE_LIMITED"
            message = "请求过于频繁，请稍后再试"
            detail = {"retry_after": exc.wait}

        response = Response(build_error_payload(code, message, detail), status=http_status)
        return response

    if isinstance(exc, Http404):
        return JsonResponse(build_error_payload("COMMON_NOT_FOUND", "资源不存在"), status=404)
    if isinstance(exc, PermissionDenied):
        return JsonResponse(
            build_error_payload("COMMON_PERMISSION_DENIED", "无权限访问该资源"), status=403
        )

    # 未预期异常：服务端记录堆栈，客户端只拿到统一错误体
    logger.exception(
        "未处理异常：%s",
        exc,
        extra={"action": "unhandled_exception", "error_code": "COMMON_INTERNAL_ERROR"},
    )
    return Response(
        build_error_payload("COMMON_INTERNAL_ERROR", "服务内部错误"),
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def not_found_handler(request, exception=None):  # noqa: ARG001
    """Django 404（非 DRF 路由）。"""
    return JsonResponse(build_error_payload("COMMON_NOT_FOUND", "资源不存在"), status=404)


def server_error_handler(request):  # noqa: ARG001
    """Django 500（非 DRF 异常）。"""
    logger.exception(
        "Django 未处理异常",
        extra={"action": "unhandled_exception", "error_code": "COMMON_INTERNAL_ERROR"},
    )
    return JsonResponse(build_error_payload("COMMON_INTERNAL_ERROR", "服务内部错误"), status=500)
