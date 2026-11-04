"""结构化日志：JSON 行格式（字段规范见架构文档 5.7）。"""

import json
import logging
import time
from datetime import UTC, datetime

from apps.common.request_id import get_request_id

_RESERVED = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "asctime",
        "taskName",
    }
)


class RequestIDFilter(logging.Filter):
    """把当前请求的 request_id 注入日志记录。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = get_request_id() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """输出单行 JSON，禁止敏感字段（由调用方保证 extra 内容）。"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).astimezone().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "module": record.module,
            "action": getattr(record, "action", record.funcName),
            "duration_ms": getattr(record, "duration_ms", None),
            "result": getattr(record, "result", None),
            "error_code": getattr(record, "error_code", None),
            "user_id": getattr(record, "user_id", None),
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key not in payload and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def duration_ms(started_at: float) -> int:
    """返回从 started_at 到现在的毫秒数。"""
    return int((time.monotonic() - started_at) * 1000)
