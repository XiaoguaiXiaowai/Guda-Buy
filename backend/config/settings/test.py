"""测试环境：独立测试库、内存缓存、关闭限流、Celery 同步执行。"""

import tempfile

from .base import *  # noqa: F403

DEBUG = False

DATABASES["default"]["TEST"] = {"NAME": "guda_test", "CHARSET": "utf8mb4"}  # noqa: F405
DATABASES["default"]["PASSWORD"] = env.str("DB_PASSWORD", default=DATABASES["default"]["PASSWORD"])  # noqa: F405

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "guda-test",
    }
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []  # noqa: F405
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {}  # noqa: F405

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

LOG_DIR = tempfile.mkdtemp(prefix="guda-test-logs-")
LOGGING["handlers"]["app_file"]["filename"] = LOG_DIR + "/app.log"  # noqa: F405
LOGGING["handlers"]["error_file"]["filename"] = LOG_DIR + "/error.log"  # noqa: F405
