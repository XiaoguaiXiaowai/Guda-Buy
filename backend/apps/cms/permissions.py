"""CMS 后台权限：运营、管理员或具备 cms.change_page 权限。"""

from rest_framework.permissions import BasePermission


class IsCmsStaff(BasePermission):
    message = "无权限访问内容后台"

    def has_permission(self, request, view) -> bool:  # noqa: ARG002
        user = request.user
        if user is None or not user.is_authenticated:
            return False
        if user.is_superuser or user.groups.filter(name="admin").exists():
            return True
        if user.groups.filter(name="operator").exists():
            return True
        return user.has_perm("cms.change_page")


class CanPublishPage(BasePermission):
    message = "无权限发布或下线内容"

    def has_permission(self, request, view) -> bool:  # noqa: ARG002
        user = request.user
        if user is None or not user.is_authenticated:
            return False
        if user.is_superuser or user.groups.filter(name="admin").exists():
            return True
        if user.groups.filter(name="operator").exists():
            return True
        return user.has_perm("cms.publish_page")
