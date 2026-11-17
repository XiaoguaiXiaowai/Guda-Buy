import threading
from decimal import Decimal

from django.db import connection
from django.test import TransactionTestCase

from apps.accounts.models import User
from apps.cart import services
from apps.cart.models import CartItem
from apps.catalog.models import Category, Product, Sku


class CartConcurrencyTests(TransactionTestCase):
    """并发加购不得产生重复行或丢失数量（唯一约束 + SKU 行锁）。"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="cart_concurrent",
            email="cart_concurrent@example.com",
            password="Passw0rd123",
        )
        category = Category.objects.create(name="女装")
        product = Product.objects.create(
            category=category,
            name="并发测试商品",
            status=Product.Status.ON_SALE,
            price_min=Decimal("99.00"),
            price_max=Decimal("99.00"),
        )
        self.sku = Sku.objects.create(
            product=product,
            sku_code="CONCUR-001",
            spec_text="默认",
            sale_price=Decimal("99.00"),
            stock=100,
            stock_capacity=100,
        )

    def test_concurrent_add_same_sku_keeps_single_row(self):
        errors = []
        thread_count = 8

        def worker():
            try:
                services.add_item(self.user, self.sku.public_id, 1)
            except Exception as exc:  # noqa: BLE001 - 测试需要收集线程内异常
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(thread_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        items = CartItem.objects.filter(user=self.user, sku=self.sku)
        assert items.count() == 1
        assert items.get().quantity == thread_count
