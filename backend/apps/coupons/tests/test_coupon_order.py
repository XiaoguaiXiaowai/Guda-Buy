"""结算与订单链路用券：预览、下单锁券、取消退券、支付核销。"""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.coupons.models import Coupon, UserCoupon
from apps.coupons.tests.conftest import make_coupon, make_user_coupon
from apps.orders import services
from apps.orders.models import Order
from apps.orders.tests.conftest import make_cart_item
from apps.payments import services as payment_services


def _preview(client, cart_item, address, coupon=None):
    payload = {
        "cart_item_public_ids": [cart_item.public_id],
        "address_public_id": address.public_id,
    }
    if coupon is not None:
        payload["user_coupon_public_id"] = coupon.public_id
    return client.post("/api/v1/orders/preview/", payload, format="json")


def _create(client, cart_item, address, coupon=None, key="coupon-order-key"):
    payload = {
        "cart_item_public_ids": [cart_item.public_id],
        "address_public_id": address.public_id,
    }
    if coupon is not None:
        payload["user_coupon_public_id"] = coupon.public_id
    return client.post("/api/v1/orders/", payload, format="json", headers={"Idempotency-Key": key})


def test_preview_lists_coupons_with_reason(auth_client, user, cart_item, address):
    make_user_coupon(user, make_coupon(name="可用券"))
    make_user_coupon(user, make_coupon(name="门槛券", min_amount="1000.00"))

    response = _preview(auth_client, cart_item, address)
    assert response.status_code == 200
    body = response.json()
    assert body["discount_amount"] == "0.00"
    assert body["payable_amount"] == "120.00"
    rows = {row["name"]: row for row in body["coupons"]}
    assert rows["可用券"]["usable"] is True
    assert rows["可用券"]["discount_amount"] == "20.00"
    assert rows["门槛券"]["usable"] is False
    assert rows["门槛券"]["reason"] == "未满 1000.00 元"


def test_preview_with_selected_coupon(auth_client, user, cart_item, address):
    user_coupon = make_user_coupon(user, make_coupon())
    response = _preview(auth_client, cart_item, address, coupon=user_coupon)
    assert response.status_code == 200
    body = response.json()
    assert body["items_amount"] == "120.00"
    assert body["discount_amount"] == "20.00"
    assert body["shipping_amount"] == "0.00"
    assert body["payable_amount"] == "100.00"
    assert body["coupon"]["user_coupon_id"] == user_coupon.public_id


def test_preview_with_invalid_coupon_returns_reason(auth_client, user, cart_item, address):
    user_coupon = make_user_coupon(user, make_coupon(min_amount="1000.00"))
    response = _preview(auth_client, cart_item, address, coupon=user_coupon)
    assert response.status_code == 200
    body = response.json()
    assert body["coupon"]["usable"] is False
    assert body["coupon"]["reason"] == "未满 1000.00 元"
    assert body["discount_amount"] == "0.00"
    assert body["payable_amount"] == "120.00"


def test_preview_free_shipping_coupon(auth_client, user, other_sku, address):
    item = make_cart_item(user, other_sku, quantity=1)
    user_coupon = make_user_coupon(
        user, make_coupon(coupon_type=Coupon.Type.FREE_SHIPPING, value="0", min_amount="0")
    )
    response = _preview(auth_client, item, address, coupon=user_coupon)
    assert response.status_code == 200
    body = response.json()
    assert body["discount_amount"] == "0.00"
    assert body["shipping_amount"] == "0.00"
    assert body["payable_amount"] == "50.00"


def test_create_order_locks_coupon(auth_client, user, cart_item, address):
    user_coupon = make_user_coupon(user, make_coupon())
    response = _create(auth_client, cart_item, address, coupon=user_coupon)
    assert response.status_code == 201
    body = response.json()
    assert body["items_amount"] == "120.00"
    assert body["discount_amount"] == "20.00"
    assert body["payable_amount"] == "100.00"
    assert body["coupon"]["public_id"] == user_coupon.public_id

    order = Order.objects.get(order_no=body["order_no"])
    assert order.user_coupon_id == user_coupon.id
    assert order.payable_amount == Decimal("100.00")
    assert order.payments.first().amount == Decimal("100.00")

    user_coupon.refresh_from_db()
    assert user_coupon.status == UserCoupon.Status.LOCKED
    assert user_coupon.order_id == order.id


def test_create_order_rejects_coupon_in_use(auth_client, user, sku, address):
    user_coupon = make_user_coupon(user, make_coupon())
    first = make_cart_item(user, sku, quantity=1)
    assert _create(auth_client, first, address, coupon=user_coupon, key="k1").status_code == 201

    second = make_cart_item(user, sku, quantity=1)
    response = _create(auth_client, second, address, coupon=user_coupon, key="k2")
    assert response.status_code == 409
    assert response.json()["code"] == "COUPON_STATUS_CONFLICT"
    assert Order.objects.filter(user=user).count() == 1


def test_create_order_with_expired_coupon_fails(auth_client, user, cart_item, address):
    user_coupon = make_user_coupon(
        user, make_coupon(), expires_at=timezone.now() - timedelta(seconds=1)
    )
    response = _create(auth_client, cart_item, address, coupon=user_coupon)
    assert response.status_code == 422
    assert response.json()["code"] == "COUPON_EXPIRED"
    assert Order.objects.filter(user=user).count() == 0
    assert user_coupon.status == UserCoupon.Status.UNUSED


def test_create_order_idempotent_replay_with_coupon(auth_client, user, cart_item, address):
    user_coupon = make_user_coupon(user, make_coupon())
    first = _create(auth_client, cart_item, address, coupon=user_coupon, key="same-key")
    assert first.status_code == 201
    replay = _create(auth_client, cart_item, address, coupon=user_coupon, key="same-key")
    assert replay.status_code == 200
    assert replay.json()["order_no"] == first.json()["order_no"]


def test_create_order_same_key_different_coupon_conflicts(auth_client, user, sku, address):
    user_coupon = make_user_coupon(user, make_coupon())
    other_coupon = make_user_coupon(user, make_coupon(name="另一张"))
    item = make_cart_item(user, sku, quantity=1)
    assert _create(auth_client, item, address, coupon=user_coupon, key="dup").status_code == 201
    item2 = make_cart_item(user, sku, quantity=1)
    response = _create(auth_client, item2, address, coupon=other_coupon, key="dup")
    assert response.status_code == 409
    assert response.json()["code"] == "ORDER_IDEMPOTENT_REPLAY"


def test_cancel_order_returns_coupon(auth_client, user, cart_item, address):
    user_coupon = make_user_coupon(user, make_coupon())
    created = _create(auth_client, cart_item, address, coupon=user_coupon).json()
    response = auth_client.post(f"/api/v1/orders/{created['order_no']}/cancel/")
    assert response.status_code == 200

    user_coupon.refresh_from_db()
    assert user_coupon.status == UserCoupon.Status.UNUSED
    assert user_coupon.order_id is None
    assert Order.objects.get(order_no=created["order_no"]).user_coupon_id == user_coupon.id


def test_timeout_cancel_returns_coupon(user, cart_item, address):
    user_coupon = make_user_coupon(user, make_coupon())
    order, _ = services.create_order(
        user,
        cart_item_public_ids=[cart_item.public_id],
        address_public_id=address.public_id,
        remark="",
        idempotency_key="timeout-key",
        user_coupon_public_id=user_coupon.public_id,
    )
    Order.objects.filter(pk=order.pk).update(pay_expires_at=timezone.now() - timedelta(minutes=1))
    assert services.cancel_timeout_order(order.id) is True

    user_coupon.refresh_from_db()
    assert user_coupon.status == UserCoupon.Status.UNUSED
    assert user_coupon.order_id is None


def test_timeout_cancel_marks_expired_coupon(user, cart_item, address):
    user_coupon = make_user_coupon(user, make_coupon())
    order, _ = services.create_order(
        user,
        cart_item_public_ids=[cart_item.public_id],
        address_public_id=address.public_id,
        remark="",
        idempotency_key="timeout-expired",
        user_coupon_public_id=user_coupon.public_id,
    )
    UserCoupon.objects.filter(pk=user_coupon.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    Order.objects.filter(pk=order.pk).update(pay_expires_at=timezone.now() - timedelta(minutes=1))
    services.cancel_timeout_order(order.id)

    user_coupon.refresh_from_db()
    assert user_coupon.status == UserCoupon.Status.EXPIRED


def test_payment_success_marks_coupon_used(auth_client, user, cart_item, address):
    user_coupon = make_user_coupon(user, make_coupon())
    created = _create(auth_client, cart_item, address, coupon=user_coupon).json()
    order = Order.objects.get(order_no=created["order_no"])
    payment_services._apply_success(order.payments.first().id, {"transaction_ref": "T-COUPON"})

    user_coupon.refresh_from_db()
    assert user_coupon.status == UserCoupon.Status.USED
    assert user_coupon.used_at is not None
    assert user_coupon.order_id == order.id


def test_order_detail_and_coupon_trial(auth_client, user, cart_item, address):
    user_coupon = make_user_coupon(user, make_coupon(name="下单券"))
    make_user_coupon(user, make_coupon(name="另一张"))
    created = _create(auth_client, cart_item, address, coupon=user_coupon).json()

    detail = auth_client.get(f"/api/v1/orders/{created['order_no']}/").json()
    assert detail["coupon"]["name"] == "下单券"
    assert detail["discount_amount"] == "20.00"

    trial = auth_client.get(f"/api/v1/orders/{created['order_no']}/coupons/")
    assert trial.status_code == 200
    body = trial.json()
    assert body["order_no"] == created["order_no"]
    assert body["coupon"]["public_id"] == user_coupon.public_id
    assert [row["name"] for row in body["coupons"]] == ["另一张"]


def test_order_coupon_trial_hides_other_users_order(auth_client, other_client, cart_item, address):
    created = _create(auth_client, cart_item, address).json()
    response = other_client.get(f"/api/v1/orders/{created['order_no']}/coupons/")
    assert response.status_code == 404
    assert response.json()["code"] == "ORDER_NOT_FOUND"
