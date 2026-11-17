"""支付后台权限：仅运营/管理员可查看支付流水。"""

from rest_framework.permissions import BasePermission


class CanViewPayments(BasePermission):
    message = "无权限查看支付流水"

    def has_permission(self, request, view) -> bool:  # noqa: ARG002
        user = request.user
        if user is None or not user.is_authenticated:
            return False
        if user.is_superuser or user.groups.filter(name__in={"admin", "operator"}).exists():
            return True
        return user.has_perm("payments.view_payment")
