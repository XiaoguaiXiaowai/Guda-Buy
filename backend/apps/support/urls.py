"""客服路由，统一挂载在 /api/v1/。"""

from django.urls import path

from apps.support import api

app_name = "support"

urlpatterns = [
    path(
        "support/conversations/",
        api.MyConversationListView.as_view(),
        name="conversation-list",
    ),
    path(
        "support/conversations/<str:public_id>/messages/",
        api.ConversationMessageView.as_view(),
        name="conversation-messages",
    ),
    path(
        "admin/support/conversations/",
        api.AdminConversationListView.as_view(),
        name="admin-conversation-list",
    ),
    path(
        "admin/support/conversations/<str:public_id>/assign/",
        api.AdminConversationAssignView.as_view(),
        name="admin-conversation-assign",
    ),
    path(
        "admin/support/conversations/<str:public_id>/close/",
        api.AdminConversationCloseView.as_view(),
        name="admin-conversation-close",
    ),
]
