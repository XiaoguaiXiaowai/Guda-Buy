"""支付回调：成功/失败状态机、幂等、金额与签名校验、库存扣减（V6-2～V6-7）。"""

from decimal import Decimal

from django.utils import timezone

from apps.orders.models import Order, OrderStatusLog
from apps.payments.models import Payment
from apps.payments.services import sign_payment
from apps.payments.tests.conftest import make_order

CALLBACK_URL = "/api/v1/payments/callback/"


def _callback(
    client,
    payment,
    *,
    status="SUCCESS",
    amount=None,
    signature=None,
    transaction_ref="MOCK-TRX-001",
):
    amount_text = amount if amount is not None else f"{payment.amount:.2f}"
    sign = signature if signature is not None else sign_payment(payment.payment_no, amount_text)
    payload = {
        "payment_no": payment.payment_no,
        "amount": amount_text,
        "status": status,
        "signature": sign,
    }
    if transaction_ref:
        payload["transaction_ref"] = transaction_ref
    return client.post(CALLBACK_URL, payload, format="json")


def test_callback_success_updates_payment_order_and_stock(client, order, sku, pending_payment):
    paid_at_before = order.paid_at

    response = _callback(client, pending_payment)

    assert response.status_code == 200
    body = response.data
    assert body["payment_no"] == pending_payment.payment_no
    assert body["status"] == "SUCCESS"
    assert body["order_status"] == "PAID"
    assert body["paid_at"]

    pending_payment.refresh_from_db()
    order.refresh_from_db()
    sku.refresh_from_db()
    assert pending_payment.status == Payment.Status.SUCCESS
    assert pending_payment.paid_at is not None
    assert pending_payment.transaction_ref == "MOCK-TRX-001"
    assert pending_payment.callback_payload == {
        "payment_no": pending_payment.payment_no,
        "amount": "198.00",
        "status": "SUCCESS",
        "transaction_ref": "MOCK-TRX-001",
    }
    assert order.status == Order.Status.PAID
    assert order.paid_at is not None
    assert paid_at_before is None
    assert sku.stock == 8
    assert sku.locked_stock == 0
    # 销量由确认收货累加，支付回调不得增加
    sku.product.refresh_from_db()
    assert sku.product.sales_count == 0
    assert OrderStatusLog.objects.filter(order=order, to_status=Order.Status.PAID).count() == 1


def test_callback_is_idempotent_for_repeated_success(client, order, sku, pending_payment):
    for _ in range(3):
        response = _callback(client, pending_payment)
        assert response.status_code == 200

    sku.refresh_from_db()
    order.refresh_from_db()
    assert sku.stock == 8
    assert sku.locked_stock == 0
    assert order.status == Order.Status.PAID
    assert Payment.objects.filter(order=order, status=Payment.Status.SUCCESS).count() == 1
    assert OrderStatusLog.objects.filter(order=order, to_status=Order.Status.PAID).count() == 1


def test_callback_rejects_bad_signature(client, order, sku, pending_payment):
    response = _callback(client, pending_payment, signature="0" * 64)

    assert response.status_code == 401
    assert response.data["code"] == "PAYMENT_SIGNATURE_INVALID"
    pending_payment.refresh_from_db()
    order.refresh_from_db()
    sku.refresh_from_db()
    assert pending_payment.status == Payment.Status.PENDING
    assert order.status == Order.Status.PENDING_PAYMENT
    assert sku.stock == 10
    assert sku.locked_stock == 2


def test_callback_rejects_tampered_amount(client, order, sku, pending_payment):
    tampered = f"{pending_payment.amount - Decimal('1.00'):.2f}"

    response = _callback(client, pending_payment, amount=tampered)

    assert response.status_code == 422
    assert response.data["code"] == "PAYMENT_AMOUNT_MISMATCH"
    assert response.data["detail"]["expected"] == "198.00"
    order.refresh_from_db()
    assert order.status == Order.Status.PENDING_PAYMENT
    sku.refresh_from_db()
    assert sku.stock == 10
    assert sku.locked_stock == 2


def test_callback_failure_keeps_order_pending(client, order, sku, pending_payment):
    response = _callback(client, pending_payment, status="FAILED")

    assert response.status_code == 200
    assert response.data["status"] == "FAILED"
    assert response.data["order_status"] == "PENDING_PAYMENT"
    pending_payment.refresh_from_db()
    order.refresh_from_db()
    sku.refresh_from_db()
    assert pending_payment.status == Payment.Status.FAILED
    assert order.status == Order.Status.PENDING_PAYMENT
    assert sku.stock == 10
    assert sku.locked_stock == 2


def test_callback_failure_is_idempotent(client, pending_payment):
    first = _callback(client, pending_payment, status="FAILED")
    second = _callback(client, pending_payment, status="FAILED")

    assert first.status_code == 200
    assert second.status_code == 200
    pending_payment.refresh_from_db()
    assert pending_payment.status == Payment.Status.FAILED


def test_failed_payment_cannot_turn_success(client, pending_payment):
    _callback(client, pending_payment, status="FAILED")

    response = _callback(client, pending_payment, status="SUCCESS")

    assert response.status_code == 409
    assert response.data["code"] == "PAYMENT_STATUS_CONFLICT"


def test_failure_then_repay_succeeds(client, auth_client, order, sku, pending_payment):
    _callback(client, pending_payment, status="FAILED")

    start = auth_client.post(
        f"/api/v1/payments/{order.order_no}/mock-pay/",
        {"channel": "ALIPAY_MOCK"},
        format="json",
    )
    assert start.status_code == 200
    new_payment = Payment.objects.get(order=order, status=Payment.Status.PENDING)
    assert new_payment.payment_no != pending_payment.payment_no

    response = _callback(client, new_payment)

    assert response.status_code == 200
    order.refresh_from_db()
    sku.refresh_from_db()
    pending_payment.refresh_from_db()
    new_payment.refresh_from_db()
    assert order.status == Order.Status.PAID
    assert sku.stock == 8
    assert sku.locked_stock == 0
    assert pending_payment.status == Payment.Status.FAILED
    assert new_payment.status == Payment.Status.SUCCESS


def test_callback_rejects_closed_payment(client, pending_payment):
    Payment.objects.filter(pk=pending_payment.pk).update(status=Payment.Status.CLOSED)

    response = _callback(client, pending_payment)

    assert response.status_code == 422
    assert response.data["code"] == "PAYMENT_CLOSED"


def test_callback_rejects_unknown_payment(client, db):
    payment = Payment(
        payment_no="PAYNOTEXIST0000000001",
        amount=Decimal("1.00"),
        status=Payment.Status.PENDING,
    )

    response = _callback(client, payment)

    assert response.status_code == 404
    assert response.data["code"] == "PAYMENT_NOT_FOUND"


def test_callback_success_then_failure_conflicts(client, pending_payment):
    _callback(client, pending_payment)

    response = _callback(client, pending_payment, status="FAILED")

    assert response.status_code == 409
    assert response.data["code"] == "PAYMENT_STATUS_CONFLICT"


def test_callback_rejects_cancelled_order(client, order, pending_payment):
    Order.objects.filter(pk=order.pk).update(status=Order.Status.CANCELLED)

    response = _callback(client, pending_payment)

    assert response.status_code == 422
    assert response.data["code"] == "PAYMENT_CLOSED"


def test_callback_on_already_paid_order_conflicts(client, pending_payment):
    Order.objects.filter(pk=pending_payment.order_id).update(
        status=Order.Status.PAID, paid_at=timezone.now()
    )

    response = _callback(client, pending_payment)

    assert response.status_code == 409
    assert response.data["code"] == "PAYMENT_ALREADY_PAID"
    pending_payment.refresh_from_db()
    assert pending_payment.status == Payment.Status.PENDING


def test_callback_rejects_invalid_status(client, pending_payment):
    response = client.post(
        CALLBACK_URL,
        {
            "payment_no": pending_payment.payment_no,
            "amount": "198.00",
            "status": "UNKNOWN",
            "signature": "x",
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "COMMON_VALIDATION_ERROR"


def test_callback_generates_transaction_ref_when_absent(client, pending_payment):
    response = _callback(client, pending_payment, transaction_ref="")

    assert response.status_code == 200
    pending_payment.refresh_from_db()
    assert pending_payment.transaction_ref.startswith("MOCK")


def test_payment_does_not_increase_sales_until_confirm(client, auth_client, user, address, sku):
    order = make_order(user, address, sku)
    payment = order.payments.get()
    _callback(client, payment)

    sku.product.refresh_from_db()
    assert sku.product.sales_count == 0

    Order.objects.filter(pk=order.pk).update(status=Order.Status.SHIPPED, shipped_at=timezone.now())
    confirm = auth_client.post(f"/api/v1/orders/{order.order_no}/confirm/", format="json")
    assert confirm.status_code == 200
    sku.product.refresh_from_db()
    assert sku.product.sales_count == 2
