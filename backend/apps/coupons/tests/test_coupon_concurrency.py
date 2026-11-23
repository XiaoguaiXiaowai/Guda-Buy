"""并发领券：总量控制不得超发。"""

from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connections

from apps.accounts.models import User
from apps.common.exceptions import BusinessError
from apps.coupons import services
from apps.coupons.models import UserCoupon
from apps.coupons.tests.conftest import make_coupon


def _claim(user, public_id):
    try:
        services.claim_coupon(user, public_id)
        return "ok"
    except BusinessError as exc:
        return exc.code
    finally:
        connections.close_all()


@pytest.mark.django_db(transaction=True)
def test_concurrent_claims_never_oversell():
    coupon = make_coupon(total_quantity=5, per_user_limit=1)
    users = [
        User.objects.create_user(
            username=f"coupon_race_{index}",
            email=f"coupon_race_{index}@example.com",
            password="Passw0rd123",
        )
        for index in range(20)
    ]

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda user: _claim(user, coupon.public_id), users))

    assert results.count("ok") == 5
    assert results.count("COUPON_SOLD_OUT") == 15
    coupon.refresh_from_db()
    assert coupon.claimed_quantity == 5
    assert UserCoupon.objects.filter(coupon=coupon).count() == 5
