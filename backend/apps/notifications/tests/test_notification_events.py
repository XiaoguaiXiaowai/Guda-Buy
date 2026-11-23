"""业务事件 → 站内消息：支付、发货、取消、超时与券到期。"""

from datetime import timedelta

from django.utils import timezone

from apps.coupons.tasks import remind_expiring_coupons
from apps.coupons.tests.conftest import make_coupon, make_user_coupon
from apps.notifications.models import Notification
from apps.orders import services as order_services
from apps.orders.models import Order
from apps.orders.tests.conftest import build_order
from apps.payments import services as payment_services
from apps.payments.models import Payment
from apps.payments.signature import sign_payment
from apps.payments.tests.conftest import make_order


def _success_callback(payment):
    return {
        "payment_no": payment.payment_no,
        "amount": f"{payment.amount:.2f}",
        "status": "SUCCESS",
        "transaction_ref": "MOCKNOTIFY0001",
        "signature": sign_payment(payment.payment_no, payment.amount),
    }


def test_payment_success_creates_order_paid_message(
    user, address, sku, django_capture_on_commit_callbacks
):
    order = make_order(user, address, sku)
    payment = order.payments.get(status=Payment.Status.PENDING)

    with django_capture_on_commit_callbacks(execute=True):
        payment_services.handle_callback(_success_callback(payment))

    notification = Notification.objects.get(user=user, type=Notification.Type.ORDER_PAID)
    assert order.order_no in notification.title
    assert notification.biz_type == "ORDER"
    assert notification.biz_public_id == order.order_no
    assert notification.is_read is False


def test_ship_order_creates_shipped_message(user, address, sku, django_capture_on_commit_callbacks):
    order = build_order(user, address, sku, status=Order.Status.PAID)

    with django_capture_on_commit_callbacks(execute=True):
        order_services.ship_order(order.order_no, "SF1234567890", user)

    notification = Notification.objects.get(user=user, type=Notification.Type.ORDER_SHIPPED)
    assert "SF1234567890" in notification.content
    assert order.order_no in notification.title


def test_user_cancel_creates_cancelled_message(
    user, address, sku, django_capture_on_commit_callbacks
):
    order = build_order(user, address, sku)

    with django_capture_on_commit_callbacks(execute=True):
        order_services.cancel_order(user, order.order_no, reason="用户取消")

    notification = Notification.objects.get(user=user, type=Notification.Type.ORDER_CANCELLED)
    assert "用户取消" in notification.content
    assert order.order_no in notification.title


def test_timeout_cancel_creates_message_once(
    user, address, sku, django_capture_on_commit_callbacks
):
    order = build_order(user, address, sku)
    order.pay_expires_at = timezone.now() - timedelta(minutes=1)
    order.save(update_fields=["pay_expires_at"])

    with django_capture_on_commit_callbacks(execute=True):
        assert order_services.cancel_timeout_order(order.pk) is True
    with django_capture_on_commit_callbacks(execute=True):
        assert order_services.cancel_timeout_order(order.pk) is False

    grabbed = Notification.objects.filter(user=user, type=Notification.Type.ORDER_CANCELLED)
    assert grabbed.count() == 1
    assert "支付超时" in grabbed.first().content


def test_notification_content_excludes_address_and_phone(
    user, address, sku, django_capture_on_commit_callbacks
):
    order = build_order(user, address, sku)

    with django_capture_on_commit_callbacks(execute=True):
        order_services.cancel_order(user, order.order_no)

    notification = Notification.objects.get(user=user, type=Notification.Type.ORDER_CANCELLED)
    assert address.phone not in notification.content
    assert address.detail not in notification.content


def test_coupon_expiring_task_creates_message_once(user):
    user_coupon = make_user_coupon(
        user, make_coupon(name="即将到期券"), expires_at=timezone.now() + timedelta(days=2)
    )

    assert remind_expiring_coupons() == 1
    assert remind_expiring_coupons() == 0

    notification = Notification.objects.get(user=user, type=Notification.Type.COUPON_EXPIRING)
    assert "即将到期券" in notification.content
    assert notification.biz_type == "USER_COUPON"
    assert notification.biz_public_id == user_coupon.public_id
