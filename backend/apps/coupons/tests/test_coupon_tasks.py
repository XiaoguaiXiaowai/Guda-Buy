"""优惠券定时任务：过期置位与到期前扫描。"""

from datetime import timedelta

from django.utils import timezone

from apps.coupons import services, tasks
from apps.coupons.models import UserCoupon
from apps.coupons.tests.conftest import make_coupon, make_user_coupon
from apps.orders.tests.conftest import build_order


def test_expire_task_only_touches_unused_expired(user, other_user, address, sku):
    now = timezone.now()
    expired_unused = make_user_coupon(
        user, make_coupon(name="过期未用"), expires_at=now - timedelta(days=1)
    )
    valid_unused = make_user_coupon(
        user, make_coupon(name="仍有效"), expires_at=now + timedelta(days=1)
    )
    order = build_order(user, address, sku)
    used = make_user_coupon(
        other_user,
        make_coupon(name="已用"),
        status=UserCoupon.Status.USED,
        used_at=now - timedelta(days=2),
        order=order,
        expires_at=now - timedelta(days=1),
    )

    assert tasks.expire_user_coupons() == 1

    expired_unused.refresh_from_db()
    valid_unused.refresh_from_db()
    used.refresh_from_db()
    assert expired_unused.status == UserCoupon.Status.EXPIRED
    assert valid_unused.status == UserCoupon.Status.UNUSED
    assert used.status == UserCoupon.Status.USED


def test_expire_task_is_idempotent(user):
    make_user_coupon(user, make_coupon(), expires_at=timezone.now() - timedelta(minutes=1))
    assert tasks.expire_user_coupons() == 1
    assert tasks.expire_user_coupons() == 0


def test_remind_expiring_coupons_returns_count(user):
    now = timezone.now()
    soon = make_user_coupon(user, make_coupon(name="即将过期"), expires_at=now + timedelta(days=2))
    make_user_coupon(user, make_coupon(name="还早"), expires_at=now + timedelta(days=10))

    assert tasks.remind_expiring_coupons() == 1
    assert services.expiring_user_coupons(3) == [soon]
