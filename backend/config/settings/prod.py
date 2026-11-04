"""生产环境（Ubuntu 24.04 LTS）。"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False

# 生产必须显式提供密钥，缺失时启动失败并给出明确提示
_secret_key = env.str("DJANGO_SECRET_KEY", default="")  # noqa: F405
if not _secret_key or _secret_key == "insecure-dev-only-secret-key":
    raise ImproperlyConfigured(
        "生产环境缺少环境变量 DJANGO_SECRET_KEY（或仍为示例值），"
        "请通过 /srv/guda/env/.env 注入随机密钥。"
    )
SECRET_KEY = _secret_key

_allowed_hosts = env.list("DJANGO_ALLOWED_HOSTS", default=[])  # noqa: F405
if not _allowed_hosts:
    raise ImproperlyConfigured(
        "生产环境缺少环境变量 DJANGO_ALLOWED_HOSTS（逗号分隔的域名白名单）。"
    )
ALLOWED_HOSTS = _allowed_hosts

# 生产不开启跨域
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = []

# 安全响应头
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

# 静态文件由 Nginx 直出
STATIC_ROOT = "/srv/guda/static"
MEDIA_ROOT = "/srv/guda/media"
