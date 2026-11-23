"""评价后台权限：运营/管理员或具备评价审核权限者可审核评价。"""

from rest_framework.permissions import BasePermission


class CanManageReviews(BasePermission):
    message = "无权限审核评价"

    def has_permission(self, request, view) -> bool:  # noqa: ARG002
        user = request.user
        if user is None or not user.is_authenticated:
            return False
        if user.is_superuser or user.groups.filter(name__in={"admin", "operator"}).exists():
            return True
        return user.has_perm("reviews.change_review") or user.has_perm("reviews.approve_review")
