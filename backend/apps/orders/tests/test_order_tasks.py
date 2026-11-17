"""订单定时任务：支付超时取消与自动确认收货。"""

from datetime import timedelta

from django.utils import timezone

from apps.catalog.models import Product
from apps.orders import services, tasks
from apps.orders.models import Order
from apps.orders.tests.conftest import build_order
from apps.payments.models import Payment


def _expire(order):
    Order.objects.filter(pk=order.pk).update(pay_expires_at=timezone.now() - timedelta(minutes=1))


def test_cancel_timeout_orders_cancels_and_releases(user, address, sku):
    order = build_order(user, address, sku, quantity=2, lock_stock=True)
    _expire(order)

    count = tasks.cancel_timeout_orders()

    assert count == 1
    order.refresh_from_db()
    assert order.status == Order.Status.CANCELLED
    assert order.cancel_reason == "支付超时自动取消"
    assert order.cancelled_at is not None
    assert order.status_logs.last().to_status == Order.Status.CANCELLED
    assert order.payments.get().status == Payment.Status.CLOSED
    sku.refresh_from_db()
    assert sku.locked_stock == 0

    assert tasks.cancel_timeout_orders() == 0
    sku.refresh_from_db()
    assert sku.locked_stock == 0


def test_cancel_timeout_skips_not_expired_and_non_pending(user, address, sku):
    not_expired = build_order(user, address, sku, lock_stock=True)
    paid = build_order(user, address, sku, status=Order.Status.PAID, lock_stock=True)
    _expire(paid)

    assert tasks.cancel_timeout_orders() == 0
    not_expired.refresh_from_db()
    paid.refresh_from_db()
    assert not_expired.status == Order.Status.PENDING_PAYMENT
    assert paid.status == Order.Status.PAID


def test_cancel_timeout_respects_batch_limit(user, address, sku):
    first = build_order(user, address, sku, lock_stock=True)
    second = build_order(user, address, sku, lock_stock=True)
    _expire(first)
    _expire(second)

    assert tasks.cancel_timeout_orders(limit=1) == 1
    assert tasks.cancel_timeout_orders(limit=1) == 1


def test_cancel_timeout_counts_eager_delay_result(user, address, sku):
    order = build_order(user, address, sku, lock_stock=True)
    _expire(order)

    result = tasks.cancel_timeout_orders.delay()

    assert result.get() == 1


def test_cancel_timeout_continues_when_single_order_fails(monkeypatch, user, address, sku):
    monkeypatch.setattr(
        services,
        "cancel_timeout_order",
        lambda order_id: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    order = build_order(user, address, sku, lock_stock=True)
    _expire(order)

    assert tasks.cancel_timeout_orders() == 0


def test_auto_confirm_orders_completes_and_increases_sales(user, address, sku):
    order = build_order(
        user,
        address,
        sku,
        status=Order.Status.SHIPPED,
        quantity=2,
        shipped_at=timezone.now() - timedelta(days=16),
    )

    count = tasks.auto_confirm_orders()

    assert count == 1
    order.refresh_from_db()
    assert order.status == Order.Status.COMPLETED
    assert order.completed_at is not None
    assert order.status_logs.last().remark == "发货超时自动确认收货"
    assert Product.objects.get(pk=sku.product_id).sales_count == 2

    assert tasks.auto_confirm_orders() == 0
    assert Product.objects.get(pk=sku.product_id).sales_count == 2


def test_auto_confirm_skips_orders_not_due(user, address, sku):
    recent = build_order(
        user,
        address,
        sku,
        status=Order.Status.SHIPPED,
        shipped_at=timezone.now() - timedelta(days=3),
    )
    pending = build_order(user, address, sku, status=Order.Status.PENDING_PAYMENT)

    assert tasks.auto_confirm_orders() == 0
    recent.refresh_from_db()
    pending.refresh_from_db()
    assert recent.status == Order.Status.SHIPPED
    assert pending.status == Order.Status.PENDING_PAYMENT


def test_auto_confirm_skips_without_shipped_at(user, address, sku):
    order = build_order(user, address, sku, status=Order.Status.SHIPPED, shipped_at=None)

    assert tasks.auto_confirm_orders() == 0
    order.refresh_from_db()
    assert order.status == Order.Status.SHIPPED


def test_auto_confirm_respects_batch_limit(user, address, sku):
    for _ in range(2):
        build_order(
            user,
            address,
            sku,
            status=Order.Status.SHIPPED,
            shipped_at=timezone.now() - timedelta(days=20),
        )

    assert tasks.auto_confirm_orders(limit=1) == 1
    assert tasks.auto_confirm_orders(limit=1) == 1
