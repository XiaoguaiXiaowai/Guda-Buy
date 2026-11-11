"""公共配置：所有环境共享，环境相关差异放在 dev/prod/test。"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env.str("DJANGO_SECRET_KEY", default="insecure-dev-only-secret-key")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])

# ---------------------------------------------------------------------------
# 应用
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "django_filters",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "apps.common",
    "apps.accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "apps.common.middleware.RequestIDMiddleware",
    "apps.common.middleware.AccessLogMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# 数据库（MariaDB，MySQL 兼容）
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env.str("DB_NAME", default="guda_dev"),
        "USER": env.str("DB_USER", default="guda_app"),
        "PASSWORD": env.str("DB_PASSWORD", default=""),
        "HOST": env.str("DB_HOST", default="127.0.0.1"),
        "PORT": env.str("DB_PORT", default="3306"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        "TEST": {"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_unicode_ci"},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# 缓存 / Redis（DB 划分见架构文档 3.6）
# ---------------------------------------------------------------------------
REDIS_URL = env.str("REDIS_URL", default="redis://127.0.0.1:6379/0")
REDIS_KEY_PREFIX = env.str("REDIS_KEY_PREFIX", default="guda:dev")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": REDIS_KEY_PREFIX,
        "TIMEOUT": 300,
    },
    # 验证码、限流、锁定计数等易失数据（Redis DB3，架构文档 3.6）
    "security": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env.str(
            "REDIS_SECURITY_URL", default=f"{REDIS_URL.rsplit('/', 1)[0]}/3"
        ),
        "KEY_PREFIX": REDIS_KEY_PREFIX,
        "TIMEOUT": 300,
    },
}

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env.str("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/1")
CELERY_RESULT_BACKEND = env.str("CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/2")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "Asia/Shanghai"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_ALWAYS_EAGER = False

# ---------------------------------------------------------------------------
# DRF / OpenAPI
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "600/min",
        "login": "5/min",
        "register": "3/min",
        "email_code": "3/min",
    },
    "UNAUTHENTICATED_USER": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "GUDA 在线电商网站 API",
    "DESCRIPTION": "GUDA 商城开放接口（OpenAPI 3.0）",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
}

# ---------------------------------------------------------------------------
# 认证 / 密码 / JWT
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_MINUTES", default=30)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# refresh 走 HttpOnly Cookie（架构文档 3.7）
AUTH_REFRESH_COOKIE_NAME = "refresh"
AUTH_REFRESH_COOKIE_PATH = "/api/v1/auth/"
AUTH_REFRESH_COOKIE_SECURE = not DEBUG

# 账号安全参数
AUTH_LOGIN_MAX_FAILURES = 5
AUTH_LOGIN_LOCK_MINUTES = 15
AUTH_EMAIL_CODE_TTL_SECONDS = 300
AUTH_EMAIL_CODE_RESEND_SECONDS = 60
AUTH_EMAIL_CODE_MAX_FAILURES = 5
AUTH_EMAIL_CODE_DAILY_LIMIT = 10
AUTH_PASSWORD_RESET_TTL_SECONDS = 1800

# ---------------------------------------------------------------------------
# 国际化 / 静态资源
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# ---------------------------------------------------------------------------
# 日志（JSON 行，字段规范见架构文档 5.7）
# ---------------------------------------------------------------------------
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "apps.common.logging.JsonFormatter"},
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "filters": {"request_id": {"()": "apps.common.logging.RequestIDFilter"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["request_id"],
        },
        "app_file": {
            "class": "logging.handlers.WatchedFileHandler",
            "filename": LOG_DIR / "app.log",
            "encoding": "utf-8",
            "formatter": "json",
            "filters": ["request_id"],
        },
        "error_file": {
            "class": "logging.handlers.WatchedFileHandler",
            "filename": LOG_DIR / "error.log",
            "encoding": "utf-8",
            "formatter": "json",
            "filters": ["request_id"],
            "level": "ERROR",
        },
    },
    "root": {"handlers": ["console", "app_file", "error_file"], "level": "INFO"},
    "loggers": {
        "guda.access": {"handlers": ["app_file"], "level": "INFO", "propagate": False},
        "django.request": {
            "handlers": ["console", "error_file"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

# ---------------------------------------------------------------------------
# 业务参数
# ---------------------------------------------------------------------------
APP_ORDER_TIMEOUT_MINUTES = env.int("APP_ORDER_TIMEOUT_MINUTES", default=30)
APP_SITE_URL = env.str("APP_SITE_URL", default="http://localhost:5173")
PAYMENT_CALLBACK_SECRET = env.str("PAYMENT_CALLBACK_SECRET", default="")
FIELD_ENCRYPTION_KEY = env.str("FIELD_ENCRYPTION_KEY", default="")
JWT_ACCESS_MINUTES = env.int("JWT_ACCESS_MINUTES", default=30)
JWT_REFRESH_DAYS = env.int("JWT_REFRESH_DAYS", default=7)

EMAIL_HOST = env.str("MAIL_HOST", default="")
EMAIL_PORT = env.int("MAIL_PORT", default=587)
EMAIL_HOST_USER = env.str("MAIL_USER", default="")
EMAIL_HOST_PASSWORD = env.str("MAIL_PASSWORD", default="")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = env.str("MAIL_USER", default="no-reply@guda.example.com")
