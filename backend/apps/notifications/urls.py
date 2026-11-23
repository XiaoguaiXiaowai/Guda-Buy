"""站内消息路由，统一挂载在 /api/v1/。"""

from django.urls import path

from apps.notifications import api

app_name = "notifications"

urlpatterns = [
    path("notifications/", api.NotificationListView.as_view(), name="list"),
    path(
        "notifications/unread-count/",
        api.NotificationUnreadCountView.as_view(),
        name="unread-count",
    ),
    path("notifications/read-all/", api.NotificationReadAllView.as_view(), name="read-all"),
    path(
        "notifications/<str:public_id>/read/",
        api.NotificationReadView.as_view(),
        name="read",
    ),
]
