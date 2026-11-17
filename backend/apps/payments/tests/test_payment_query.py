"""支付单查询与后台流水（V6-9）。"""

from decimal import Decimal

from apps.payments.models import Payment

PAYMENT_DETAIL_URL = "/api/v1/payments/{payment_no}/"
ADMIN_PAYMENTS_URL = "/api/v1/admin/payments/"


def test_payment_detail_requires_auth(client, pending_payment):
    response = client.get(PAYMENT_DETAIL_URL.format(payment_no=pending_payment.payment_no))

    assert response.status_code == 401


def test_payment_detail_returns_own_payment(auth_client, pending_payment):
    response = auth_client.get(PAYMENT_DETAIL_URL.format(payment_no=pending_payment.payment_no))

    assert response.status_code == 200
    body = response.data
    assert body["payment_no"] == pending_payment.payment_no
    assert body["order_no"] == pending_payment.order.order_no
    assert body["amount"] == "198.00"
    assert body["status"] == "PENDING"
    assert body["channel_text"] == "支付宝（模拟）"
    assert body["transaction_ref"] == ""


def test_payment_detail_hides_other_users_payment(other_client, pending_payment):
    response = other_client.get(PAYMENT_DETAIL_URL.format(payment_no=pending_payment.payment_no))

    assert response.status_code == 404
    assert response.data["code"] == "PAYMENT_NOT_FOUND"


def test_payment_detail_unknown(auth_client, db):
    response = auth_client.get(PAYMENT_DETAIL_URL.format(payment_no="PAYUNKNOWN000000000001"))

    assert response.status_code == 404


def test_admin_payments_requires_auth(client):
    assert client.get(ADMIN_PAYMENTS_URL).status_code == 401


def test_admin_payments_forbidden_for_customer(auth_client):
    response = auth_client.get(ADMIN_PAYMENTS_URL)

    assert response.status_code == 403
    assert response.data["code"] == "COMMON_PERMISSION_DENIED"


def test_admin_payments_forbidden_for_support(support_client):
    response = support_client.get(ADMIN_PAYMENTS_URL)

    assert response.status_code == 403


def test_admin_payments_lists_and_filters(operator_client, order, pending_payment):
    success = Payment.objects.create(
        payment_no="PAYSUCCESS000000000001",
        order=order,
        channel=Payment.Channel.WECHAT_MOCK,
        amount=Decimal("198.00"),
        status=Payment.Status.SUCCESS,
    )

    listing = operator_client.get(ADMIN_PAYMENTS_URL)
    assert listing.status_code == 200
    assert listing.data["count"] == 2
    first = listing.data["results"][0]
    assert set(first) == {
        "payment_no",
        "order_no",
        "channel",
        "channel_text",
        "amount",
        "status",
        "status_text",
        "transaction_ref",
        "paid_at",
        "created_at",
        "order_status",
        "order_status_text",
        "username",
    }
    assert first["order_no"] == order.order_no
    assert first["order_status"] == "PENDING_PAYMENT"
    assert first["username"] == order.user.username

    by_order = operator_client.get(ADMIN_PAYMENTS_URL, {"order_no": order.order_no})
    assert by_order.data["count"] == 2

    by_payment = operator_client.get(ADMIN_PAYMENTS_URL, {"payment_no": pending_payment.payment_no})
    assert by_payment.data["count"] == 1
    assert by_payment.data["results"][0]["payment_no"] == pending_payment.payment_no

    by_status = operator_client.get(ADMIN_PAYMENTS_URL, {"status": "SUCCESS"})
    assert by_status.data["count"] == 1
    assert by_status.data["results"][0]["payment_no"] == success.payment_no

    by_channel = operator_client.get(ADMIN_PAYMENTS_URL, {"channel": "WECHAT_MOCK"})
    assert by_channel.data["count"] == 1

    assert operator_client.get(ADMIN_PAYMENTS_URL, {"order_no": "GD-NOT-EXIST"}).data["count"] == 0
