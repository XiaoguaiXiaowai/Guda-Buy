"""后台订单查询与发货权限。"""

from django.contrib.auth.models import Permission

from apps.accounts.models import User
from apps.orders.models import Order
from apps.orders.tests.conftest import build_order

ADMIN_LIST_URL = "/api/v1/admin/orders/"


def _ship_url(order_no):
    return f"/api/v1/admin/orders/{order_no}/ship/"


def test_admin_order_list_requires_auth(client):
    assert client.get(ADMIN_LIST_URL).status_code == 401


def test_normal_user_cannot_access_admin_orders(auth_client, user, address, sku):
    order = build_order(user, address, sku)

    assert auth_client.get(ADMIN_LIST_URL).status_code == 403
    ship_response = auth_client.post(_ship_url(order.order_no), {"tracking_no": "SF123456"})
    assert ship_response.status_code == 403


def test_support_can_read_but_not_ship(support_client, user, address, sku):
    order = build_order(user, address, sku, status=Order.Status.PAID)

    listed = support_client.get(ADMIN_LIST_URL)
    shipped = support_client.post(_ship_url(order.order_no), {"tracking_no": "SF123456"})

    assert listed.status_code == 200
    assert listed.data["count"] == 1
    assert listed.data["results"][0]["user"]["username"] == "order_user"
    assert shipped.status_code == 403


def test_operator_can_read_all_orders_and_filter(operator_client, user, other_user, address, sku):
    build_order(user, address, sku, status=Order.Status.PAID)
    build_order(other_user, address, sku, status=Order.Status.CANCELLED)

    all_orders = operator_client.get(ADMIN_LIST_URL)
    filtered = operator_client.get(ADMIN_LIST_URL, {"status": "PAID"})

    assert all_orders.status_code == 200
    assert all_orders.data["count"] == 2
    assert filtered.data["count"] == 1
    assert filtered.data["results"][0]["status"] == "PAID"


def test_operator_ships_paid_order(operator_client, operator_user, user, address, sku):
    order = build_order(user, address, sku, status=Order.Status.PAID)

    response = operator_client.post(_ship_url(order.order_no), {"tracking_no": "SF1234567890"})

    assert response.status_code == 200
    assert response.data["status"] == "SHIPPED"
    assert response.data["tracking_no"] == "SF1234567890"
    assert response.data["shipped_at"] is not None
    order.refresh_from_db()
    assert order.status == Order.Status.SHIPPED
    log = order.status_logs.last()
    assert log.to_status == Order.Status.SHIPPED
    assert log.operator == operator_user
    assert "SF1234567890" in log.remark


def test_ship_rejects_non_paid_order(operator_client, user, address, sku):
    order = build_order(user, address, sku, status=Order.Status.PENDING_PAYMENT)

    response = operator_client.post(_ship_url(order.order_no), {"tracking_no": "SF123456"})

    assert response.status_code == 409
    assert response.data["code"] == "ORDER_STATUS_CONFLICT"


def test_ship_validates_tracking_no(operator_client, user, address, sku):
    order = build_order(user, address, sku, status=Order.Status.PAID)

    missing = operator_client.post(_ship_url(order.order_no), {}, format="json")
    invalid = operator_client.post(_ship_url(order.order_no), {"tracking_no": "ab"}, format="json")

    assert missing.status_code == 400
    assert invalid.status_code == 400


def test_ship_unknown_order_returns_404(operator_client):
    response = operator_client.post(_ship_url("GD-NOT-EXISTS"), {"tracking_no": "SF123456"})

    assert response.status_code == 404
    assert response.data["code"] == "ORDER_NOT_FOUND"


def test_permission_codename_grants_access(db, user, address, sku):
    staff = User.objects.create_user(
        username="perm_user",
        email="perm@example.com",
        password="Passw0rd123",
        is_staff=True,
    )
    staff.user_permissions.add(Permission.objects.get(codename="view_all_order"))
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=staff)
    order = build_order(user, address, sku, status=Order.Status.PAID)

    listed = client.get(ADMIN_LIST_URL)
    ship_denied = client.post(_ship_url(order.order_no), {"tracking_no": "SF123456"})

    assert listed.status_code == 200
    assert ship_denied.status_code == 403

    staff.user_permissions.add(Permission.objects.get(codename="ship_order"))
    staff = User.objects.get(pk=staff.pk)
    client.force_authenticate(user=staff)
    shipped = client.post(_ship_url(order.order_no), {"tracking_no": "SF123456"})

    assert shipped.status_code == 200


def test_superuser_can_ship(db, user, address, sku):
    from rest_framework.test import APIClient

    admin = User.objects.create_superuser(
        username="root_admin", email="root@example.com", password="Passw0rd123"
    )
    client = APIClient()
    client.force_authenticate(user=admin)
    order = build_order(user, address, sku, status=Order.Status.PAID)

    response = client.post(_ship_url(order.order_no), {"tracking_no": "SF123456"})

    assert response.status_code == 200
