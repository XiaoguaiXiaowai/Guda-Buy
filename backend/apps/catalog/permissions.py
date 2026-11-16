"""商品后台权限：运营、管理员或具备 catalog.change_product 权限。"""

from rest_framework.permissions import BasePermission


class IsCatalogStaff(BasePermission):
    message = "无权限访问商品后台"

    def has_permission(self, request, view) -> bool:  # noqa: ARG002
        user = request.user
        if user is None or not user.is_authenticated:
            return False
        if user.is_superuser or user.groups.filter(name="admin").exists():
            return True
        if user.groups.filter(name="operator").exists():
            return True
        return user.has_perm("catalog.change_product")


class CanChangeStock(BasePermission):
    message = "无权限调整库存"

    def has_permission(self, request, view) -> bool:  # noqa: ARG002
        user = request.user
        if user is None or not user.is_authenticated:
            return False
        if user.is_superuser or user.groups.filter(name="admin").exists():
            return True
        return user.has_perm("catalog.change_stock")
