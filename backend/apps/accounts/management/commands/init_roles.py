"""初始化四个角色组与权限点（迭代 T1.1）。

用法：python manage.py init_roles
幂等：重复执行只补齐缺失权限，不会清空已有授权。
"""

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

ROLE_PERMISSIONS = {
    "customer": [],
    "support": [
        "orders.view_all_order",
        "support.reply_conversation",
        "support.assign_conversation",
        "accounts.view_user",
    ],
    "operator": [
        "catalog.add_product",
        "catalog.change_product",
        "catalog.delete_product",
        "catalog.change_stock",
        "cms.change_page",
        "cms.publish_page",
        "coupons.add_coupon",
        "coupons.change_coupon",
        "reviews.change_review",
        "reviews.approve_review",
        "orders.view_all_order",
        "orders.ship_order",
        "orders.refund_order",
        "payments.view_payment",
    ],
}

ROLE_LABELS = {
    "customer": "会员",
    "support": "客服",
    "operator": "运营",
    "admin": "管理员",
}


class Command(BaseCommand):
    help = "初始化角色组（customer/support/operator/admin）与权限点"

    def handle(self, *args, **options):  # noqa: ARG002
        groups = {}
        for codename, label in ROLE_LABELS.items():
            group, _ = Group.objects.get_or_create(name=codename)
            groups[codename] = group
            self.stdout.write(f"角色组 {codename}（{label}）就绪")

        all_permissions = list(Permission.objects.all())
        missing: set[str] = set()

        for role, codenames in ROLE_PERMISSIONS.items():
            group = groups[role]
            for item in codenames:
                app_label, codename = item.split(".", 1)
                permission = next(
                    (
                        perm
                        for perm in all_permissions
                        if perm.content_type.app_label == app_label
                        and perm.codename == codename
                    ),
                    None,
                )
                if permission is None:
                    missing.add(item)
                    continue
                group.permissions.add(permission)

        groups["admin"].permissions.set(all_permissions)

        if missing:
            self.stdout.write(
                self.style.WARNING(
                    "以下权限点尚未在本期建模，已跳过：" + "、".join(sorted(missing))
                )
            )
        self.stdout.write(self.style.SUCCESS("角色组与权限点初始化完成"))
