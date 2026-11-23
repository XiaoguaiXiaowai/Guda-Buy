"""优惠券后台权限：运营/管理员或具备券管理权限者可创建、修改券模板。"""

from rest_framework.permissions import BasePermission


class CanManageCoupons(BasePermission):
    message = "无权限管理优惠券"

    def has_permission(self, request, view) -> bool:  # noqa: ARG002
        user = request.user
        if user is None or not user.is_authenticated:
            return False
        if user.is_superuser or user.groups.filter(name__in={"admin", "operator"}).exists():
            return True
        return user.has_perm("coupons.add_coupon") or user.has_perm("coupons.change_coupon")
