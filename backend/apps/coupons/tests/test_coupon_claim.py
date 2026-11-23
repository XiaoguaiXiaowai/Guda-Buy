"""领券、可领列表与我的券。"""

from datetime import timedelta

from django.utils import timezone

from apps.coupons.models import Coupon, UserCoupon
from apps.coupons.tests.conftest import make_coupon, make_user_coupon
from apps.orders.tests.conftest import build_order


def test_claim_coupon_success(auth_client, user):
    coupon = make_coupon()
    response = auth_client.post(f"/api/v1/coupons/{coupon.public_id}/claim/")
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == UserCoupon.Status.UNUSED
    assert payload["coupon"]["public_id"] == coupon.public_id

    coupon.refresh_from_db()
    assert coupon.claimed_quantity == 1
    user_coupon = UserCoupon.objects.get(user=user, coupon=coupon)
    assert user_coupon.expires_at == coupon.valid_to


def test_claim_requires_auth(client, db):
    coupon = make_coupon()
    response = client.post(f"/api/v1/coupons/{coupon.public_id}/claim/")
    assert response.status_code == 401


def test_claim_unknown_coupon(auth_client, db):
    response = auth_client.post("/api/v1/coupons/not-exists/claim/")
    assert response.status_code == 404
    assert response.json()["code"] == "COUPON_NOT_FOUND"


def test_claim_respects_per_user_limit(auth_client, user):
    coupon = make_coupon(per_user_limit=2, total_quantity=10)
    assert auth_client.post(f"/api/v1/coupons/{coupon.public_id}/claim/").status_code == 201
    assert auth_client.post(f"/api/v1/coupons/{coupon.public_id}/claim/").status_code == 201
    response = auth_client.post(f"/api/v1/coupons/{coupon.public_id}/claim/")
    assert response.status_code == 422
    assert response.json()["code"] == "COUPON_LIMIT_REACHED"
    assert UserCoupon.objects.filter(user=user, coupon=coupon).count() == 2


def test_claim_sold_out(auth_client):
    coupon = make_coupon(total_quantity=1, claimed_quantity=1)
    response = auth_client.post(f"/api/v1/coupons/{coupon.public_id}/claim/")
    assert response.status_code == 422
    assert response.json()["code"] == "COUPON_SOLD_OUT"


def test_claim_rejects_inactive_coupon(auth_client):
    for status in (Coupon.Status.DRAFT, Coupon.Status.STOPPED):
        coupon = make_coupon(name=f"券-{status}", status=status)
        response = auth_client.post(f"/api/v1/coupons/{coupon.public_id}/claim/")
        assert response.status_code == 409
        assert response.json()["code"] == "COUPON_STATUS_CONFLICT"


def test_claim_rejects_not_started_and_expired(auth_client):
    now = timezone.now()
    not_started = make_coupon(
        name="未开始", valid_from=now + timedelta(days=1), valid_to=now + timedelta(days=2)
    )
    expired = make_coupon(
        name="已过期", valid_from=now - timedelta(days=2), valid_to=now - timedelta(days=1)
    )
    for coupon in (not_started, expired):
        response = auth_client.post(f"/api/v1/coupons/{coupon.public_id}/claim/")
        assert response.status_code == 422
        assert response.json()["code"] == "COUPON_EXPIRED"


def test_available_coupons_marks_reasons(auth_client, user):
    make_coupon(name="可领券")
    make_coupon(name="已领完", total_quantity=5, claimed_quantity=5)
    limit_reached = make_coupon(name="已领过", per_user_limit=1, claimed_quantity=1)
    make_user_coupon(user, limit_reached)
    make_coupon(name="草稿", status=Coupon.Status.DRAFT)
    now = timezone.now()
    make_coupon(name="已过期", valid_from=now - timedelta(days=3), valid_to=now - timedelta(days=1))

    response = auth_client.get("/api/v1/coupons/available/")
    assert response.status_code == 200
    rows = {row["name"]: row for row in response.json()}
    assert set(rows) == {"可领券", "已领完", "已领过"}
    assert rows["可领券"]["can_claim"] is True
    assert rows["已领完"]["reason"] == "已领完"
    assert rows["已领过"]["can_claim"] is False
    assert rows["已领过"]["claimed_by_me"] == 1
    assert rows["可领券"]["scope_summary"] == "全场通用"


def test_my_coupons_grouping(auth_client, user, address, sku):
    now = timezone.now()
    unused = make_coupon(name="未使用")
    used = make_coupon(name="已使用")
    expired = make_coupon(name="已过期")
    stale = make_coupon(
        name="过期未标记",
        valid_from=now - timedelta(days=3),
        valid_to=now - timedelta(days=1),
    )
    make_user_coupon(user, unused)
    order = build_order(user, address, sku)
    make_user_coupon(user, used, status=UserCoupon.Status.USED, used_at=now, order=order)
    make_user_coupon(user, expired, status=UserCoupon.Status.EXPIRED)
    make_user_coupon(user, stale)

    response = auth_client.get("/api/v1/users/me/coupons/")
    assert response.status_code == 200
    body = response.json()
    assert body["counts"] == {"unused": 1, "used": 1, "expired": 2}
    assert body["unused"][0]["coupon"]["name"] == "未使用"
    assert body["used"][0]["order_no"] == order.order_no
    assert {row["coupon"]["name"] for row in body["expired"]} == {"已过期", "过期未标记"}


def test_my_coupons_requires_auth(client, db):
    assert client.get("/api/v1/users/me/coupons/").status_code == 401
