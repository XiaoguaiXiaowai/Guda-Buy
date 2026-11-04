"""请求中间件：request_id 注入与访问日志。"""

import logging
import time
import uuid

from django.utils.deprecation import MiddlewareMixin

from apps.common.logging import duration_ms
from apps.common.request_id import get_request_id, set_request_id

access_logger = logging.getLogger("guda.access")


class RequestIDMiddleware(MiddlewareMixin):
    """为每个请求生成/透传 X-Request-ID，并写入响应头。"""

    def process_request(self, request):
        incoming = request.headers.get("X-Request-ID", "").strip()
        request_id = incoming or f"req-{uuid.uuid4().hex[:8]}"
        request.request_id = request_id
        set_request_id(request_id)
        request._guda_started_at = time.monotonic()

    def process_response(self, request, response):
        response["X-Request-ID"] = getattr(request, "request_id", None) or get_request_id() or "-"
        return response


class AccessLogMiddleware(MiddlewareMixin):
    """记录访问日志（跳过静态资源），字段见架构文档 5.7。"""

    SKIP_PREFIXES = ("/static/", "/media/")

    def process_response(self, request, response):
        path = request.path
        if path.startswith(self.SKIP_PREFIXES):
            return response

        user = getattr(request, "user", None)
        user_id = None
        if user is not None and getattr(user, "is_authenticated", False):
            user_id = getattr(user, "public_id", None) or user.pk

        started_at = getattr(request, "_guda_started_at", None)
        access_logger.info(
            "%s %s",
            request.method,
            path,
            extra={
                "action": f"{request.method.lower()}_{path}",
                "result": response.status_code,
                "duration_ms": duration_ms(started_at) if started_at else None,
                "user_id": user_id,
            },
        )
        return response
