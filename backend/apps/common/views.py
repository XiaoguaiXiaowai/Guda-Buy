"""健康检查与 API 根节点。"""

import logging

import redis
from django.conf import settings
from django.db import DatabaseError, connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import build_error_payload

logger = logging.getLogger("guda.common")


class HealthStatusSerializer(serializers.Serializer):
    status = serializers.CharField()
    db = serializers.CharField()
    redis = serializers.CharField()


def _check_database() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except DatabaseError:
        logger.exception("健康检查：数据库不可用", extra={"action": "healthz_db"})
        return False


def _check_redis() -> bool:
    client = None
    try:
        client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        return bool(client.ping())
    except Exception:  # noqa: BLE001 - 探活需要吞掉任意驱动异常
        logger.exception("健康检查：Redis 不可用", extra={"action": "healthz_redis"})
        return False
    finally:
        if client is not None:
            client.close()


class HealthCheckView(APIView):
    """GET /healthz/：校验 DB 与 Redis 连通性，任一失败返回 503。"""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    @extend_schema(
        summary="健康检查",
        description="返回数据库与 Redis 连通状态；任一依赖不可用返回 503。",
        responses={
            200: HealthStatusSerializer,
            503: inline_serializer(
                name="HealthCheckUnavailable",
                fields={
                    "code": serializers.CharField(),
                    "message": serializers.CharField(),
                    "detail": serializers.JSONField(),
                    "request_id": serializers.CharField(),
                    "timestamp": serializers.CharField(),
                },
            ),
        },
    )
    def get(self, request):  # noqa: ARG002
        db_ok = _check_database()
        redis_ok = _check_redis()

        if not (db_ok and redis_ok):
            payload = build_error_payload(
                "COMMON_SERVICE_UNAVAILABLE",
                "依赖服务不可用",
                {"db": "ok" if db_ok else "fail", "redis": "ok" if redis_ok else "fail"},
            )
            response = Response(payload, status=503)
        else:
            response = Response({"status": "ok", "db": "ok", "redis": "ok"})

        response["Cache-Control"] = "no-store"
        return response


class ApiRootSerializer(serializers.Serializer):
    service = serializers.CharField()
    version = serializers.CharField()
    status = serializers.CharField()


@extend_schema(
    summary="API 根节点",
    description="返回当前 API 版本信息。",
    responses=ApiRootSerializer,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request):  # noqa: ARG001
    return Response({"service": "guda", "version": "v1", "status": "ready"})
