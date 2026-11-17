from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny

from apps.common.views import HealthCheckView, api_root

urlpatterns = [
    path("healthz/", HealthCheckView.as_view(), name="healthz"),
    path("admin/", admin.site.urls),
]

# OpenAPI 契约与文档（生产环境仅内网/登录后开放，由 Nginx 侧限制）
urlpatterns += [
    path("api/schema/", SpectacularAPIView.as_view(permission_classes=[AllowAny]), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[AllowAny]),
        name="swagger-ui",
    ),
    path("api/v1/", api_root, name="api-root"),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/", include("apps.cms.urls")),
]

handler404 = "apps.common.exceptions.not_found_handler"
handler500 = "apps.common.exceptions.server_error_handler"

# 开发环境由 Django 直出 media；生产环境由 Nginx alias /srv/guda/media/ 提供
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
