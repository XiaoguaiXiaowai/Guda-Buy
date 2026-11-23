"""客服权限：admin/support 组、超管或具备客服权限点的用户。"""

from rest_framework.permissions import BasePermission


def is_support_staff(user) -> bool:
    """客服坐席判定：组、超管或权限点任一满足即可。"""
    if user is None or not user.is_authenticated:
        return False
    if user.is_superuser or user.groups.filter(name__in={"admin", "support"}).exists():
        return True
    return user.has_perm("support.reply_conversation") or user.has_perm(
        "support.assign_conversation"
    )


class CanManageSupportConversations(BasePermission):
    message = "无权限操作客服会话"

    def has_permission(self, request, view) -> bool:  # noqa: ARG002
        return is_support_staff(request.user)
