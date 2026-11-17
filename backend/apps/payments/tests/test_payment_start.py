"""发起支付：复用/换渠道/关闭规则与异常分支（V6-1、V6-7）。"""

from django.utils import timezone

from apps.orders.models import Order
from apps.payments.models import Payment
from apps.payments.services import sign_payment
from apps.payments.tests.conftest import make_order

MOCK_PAY_URL = "/api/v1/payments/{order_no}/mock-pay/"


def _mock_pay(client, order_no, channel=None):
    payload = {} if channel is None else {"channel": channel}
    return client.post(MOCK_PAY_URL.format(order_no=order_no), payload, format="json")


def test_mock_pay_requires_auth(client, order):
    response = _mock_pay(client, order.order_no)

    assert response.status_code == 401


def test_mock_pay_reuses_pending_payment(auth_client, order, pending_payment):
    response = _mock_pay(auth_client, order.order_no, "ALIPAY_MOCK")

    assert response.status_code == 200
    body = response.data
    assert body["payment_no"] == pending_payment.payment_no
    assert body["order_no"] == order.order_no
    assert body["amount"] == "198.00"
    assert body["channel"] == "ALIPAY_MOCK"
    assert body["channel_text"] == "支付宝（模拟）"
    assert body["status"] == "PENDING"
    assert body["sign"] == sign_payment(pending_payment.payment_no, "198.00")
    assert body["callback_url"] == "/api/v1/payments/callback/"
    assert body["demo_notice"] == "演示支付，不会产生真实扣款"
    assert body["order_pay_expires_at"]
    assert Payment.objects.filter(order=order, status=Payment.Status.PENDING).count() == 1


def test_mock_pay_switches_channel_and_closes_old(auth_client, order, pending_payment):
    response = _mock_pay(auth_client, order.order_no, "WECHAT_MOCK")

    assert response.status_code == 200
    assert response.data["payment_no"] != pending_payment.payment_no
    pending_payment.refresh_from_db()
    assert pending_payment.status == Payment.Status.CLOSED
    current = Payment.objects.get(order=order, status=Payment.Status.PENDING)
    assert current.channel == "WECHAT_MOCK"
    assert Payment.objects.filter(order=order, status=Payment.Status.PENDING).count() == 1


def test_mock_pay_defaults_to_alipay(auth_client, order, pending_payment):
    response = _mock_pay(auth_client, order.order_no)

    assert response.status_code == 200
    assert response.data["payment_no"] == pending_payment.payment_no


def test_mock_pay_rejects_cancelled_order(auth_client, order):
    Order.objects.filter(pk=order.pk).update(status=Order.Status.CANCELLED)

    response = _mock_pay(auth_client, order.order_no)

    assert response.status_code == 422
    assert response.data["code"] == "PAYMENT_CLOSED"
    assert Payment.objects.filter(order=order).count() == 1


def test_mock_pay_rejects_paid_order(auth_client, order):
    Order.objects.filter(pk=order.pk).update(status=Order.Status.PAID)

    response = _mock_pay(auth_client, order.order_no)

    assert response.status_code == 409
    assert response.data["code"] == "PAYMENT_ALREADY_PAID"


def test_mock_pay_rejects_expired_order(auth_client, order):
    Order.objects.filter(pk=order.pk).update(pay_expires_at=timezone.now() - timezone.timedelta(1))

    response = _mock_pay(auth_client, order.order_no)

    assert response.status_code == 422
    assert response.data["code"] == "PAYMENT_CLOSED"
    assert Payment.objects.filter(order=order, status=Payment.Status.PENDING).count() == 0


def test_mock_pay_hides_other_users_order(other_client, order):
    response = _mock_pay(other_client, order.order_no)

    assert response.status_code == 404
    assert response.data["code"] == "ORDER_NOT_FOUND"


def test_mock_pay_rejects_unknown_channel(auth_client, order):
    response = _mock_pay(auth_client, order.order_no, "UNKNOWN")

    assert response.status_code == 400
    assert response.data["code"] == "COMMON_VALIDATION_ERROR"


def test_mock_pay_creates_new_payment_after_failure(auth_client, user, address, sku):
    order = make_order(user, address, sku)
    failed = order.payments.get()
    Payment.objects.filter(pk=failed.pk).update(status=Payment.Status.FAILED)

    response = _mock_pay(auth_client, order.order_no, "BALANCE_MOCK")

    assert response.status_code == 200
    assert response.data["payment_no"] != failed.payment_no
    failed.refresh_from_db()
    assert failed.status == Payment.Status.FAILED
    assert Payment.objects.filter(order=order, status=Payment.Status.PENDING).count() == 1
