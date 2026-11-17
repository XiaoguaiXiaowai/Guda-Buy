"""订单后台权限：客服只读，运营/管理员可发货。"""

from rest_framework.permissions import BasePermission


def _in_groups(user, names: set[str]) -> bool:
    return user.groups.filter(name__in=names).exists()


class IsOrderSupport(BasePermission):
    message = "无权限查看订单"

    def has_permission(self, request, view) -> bool:  # noqa: ARG002
        user = request.user
        if user is None or not user.is_authenticated:
            return False
        if user.is_superuser or _in_groups(user, {"admin", "operator", "support"}):
            return True
        return user.has_perm("orders.view_all_order")


class CanShipOrder(BasePermission):
    message = "无权限发货"

    def has_permission(self, request, view) -> bool:  # noqa: ARG002
        user = request.user
        if user is None or not user.is_authenticated:
            return False
        if user.is_superuser or _in_groups(user, {"admin", "operator"}):
            return True
        return user.has_perm("orders.ship_order")
