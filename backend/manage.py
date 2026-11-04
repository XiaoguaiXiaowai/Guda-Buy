#!/usr/bin/env python
"""Django 管理入口。"""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - 环境未安装依赖时的提示
        raise ImportError(
            "无法导入 Django，请先执行 `uv sync` 并在项目根目录使用 `uv run python manage.py ...`。"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
