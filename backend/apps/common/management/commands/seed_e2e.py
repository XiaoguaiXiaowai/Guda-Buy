"""为 E2E 独立测试库准备固定数据（幂等，可重复执行）。"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

E2E_PASSWORD = "Passw0rd123"

E2E_USERS = [
    ("e2e_buyer", "e2e_buyer@guda.test", "会员小E", "customer"),
    ("e2e_operator", "e2e_operator@guda.test", "运营小E", "operator"),
    ("e2e_support", "e2e_support@guda.test", "客服小E", "support"),
]

# 压测专用账号池，避免 20 个并发用户共用一个购物车
E2E_PERF_COUNT = 20


class Command(BaseCommand):
    help = "初始化 I11 E2E 测试库数据：固定账号、分类、商品、SKU、优惠券"

    @transaction.atomic
    def handle(self, *args, **options):  # noqa: ARG002
        from apps.accounts.models import User
        from apps.catalog.models import Category, Product, Sku
        from apps.coupons.models import Coupon

        for username, email, nickname, role in E2E_USERS:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={"email": email, "nickname": nickname},
            )
            user.email = email
            user.nickname = nickname
            user.set_password(E2E_PASSWORD)
            user.save()
            group = Group.objects.filter(name=role).first()
            if group is not None:
                user.groups.add(group)

        for index in range(1, E2E_PERF_COUNT + 1):
            username = f"e2e_perf{index:02d}"
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@guda.test", "nickname": f"压测{index:02d}"},
            )
            user.set_password(E2E_PASSWORD)
            user.save()

        parent, _ = Category.objects.get_or_create(
            name="E2E 女装", parent=None, defaults={"sort_weight": 100}
        )
        child, _ = Category.objects.get_or_create(
            name="E2E 连衣裙", parent=parent, defaults={"sort_weight": 100}
        )

        product, _ = Product.objects.get_or_create(
            name="E2E 法式碎花连衣裙",
            defaults={
                "category": child,
                "subtitle": "自动化测试专用商品",
                "description": "E2E 全链路测试商品。",
                "price_min": Decimal("199.00"),
                "price_max": Decimal("209.00"),
                "status": Product.Status.ON_SALE,
                "sort_weight": 100,
            },
        )
        product.category = child
        product.status = Product.Status.ON_SALE
        product.price_min = Decimal("199.00")
        product.price_max = Decimal("209.00")
        product.save()

        sku_specs = [
            ("E2E-DRESS-WHITE-M", "米白 M", Decimal("199.00"), 1000),
            ("E2E-DRESS-BLACK-L", "黑色 L", Decimal("209.00"), 500),
        ]
        for code, spec, price, stock in sku_specs:
            sku, _ = Sku.objects.get_or_create(
                sku_code=code,
                defaults={
                    "product": product,
                    "spec_text": spec,
                    "specs": {"颜色": spec.split()[0], "尺码": spec.split()[1]},
                    "sale_price": price,
                    "original_price": price + Decimal("100.00"),
                    "stock": stock,
                    "stock_capacity": stock,
                },
            )
            sku.product = product
            sku.stock = stock
            sku.stock_capacity = max(sku.stock_capacity, stock)
            sku.status = Sku.Status.ON_SALE
            sku.save()

        now = timezone.now()
        coupon, _ = Coupon.objects.get_or_create(
            name="E2E 满 100 减 10",
            defaults={
                "coupon_type": Coupon.Type.FIXED,
                "value": Decimal("10.00"),
                "min_amount": Decimal("100.00"),
                "total_quantity": 1000,
                "claimed_quantity": 0,
                "per_user_limit": 1,
                "scope_type": Coupon.ScopeType.ALL,
                "valid_from": now - timedelta(days=1),
                "valid_to": now + timedelta(days=7),
                "status": Coupon.Status.ACTIVE,
            },
        )
        coupon.status = Coupon.Status.ACTIVE
        coupon.per_user_limit = 50
        coupon.total_quantity = 100000
        coupon.valid_from = now - timedelta(days=1)
        coupon.valid_to = now + timedelta(days=7)
        coupon.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"E2E 数据就绪：用户 {len(E2E_USERS) + E2E_PERF_COUNT} 个，"
                f"商品 {product.public_id}，SKU {len(sku_specs)} 个，优惠券 {coupon.public_id}"
            )
        )
