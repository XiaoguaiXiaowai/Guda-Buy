"""交易记录汇总：状态计数与金额汇总口径。"""

from apps.orders import selectors
from apps.orders.models import Order
from apps.orders.tests.conftest import build_order


def test_summary_counts_and_amounts_match_orders(user, other_user, address, other_address, sku):
    build_order(user, address, sku, status=Order.Status.PAID, quantity=2)
    build_order(user, address, sku, status=Order.Status.COMPLETED, quantity=1)
    build_order(user, address, sku, status=Order.Status.CANCELLED, quantity=1)
    build_order(other_user, other_address, sku, status=Order.Status.PAID, quantity=3)

    summary = selectors.order_summary(user)

    assert summary["counts"]["ALL"] == 3
    assert summary["counts"]["PAID"] == 1
    assert summary["counts"]["COMPLETED"] == 1
    assert summary["counts"]["CANCELLED"] == 1
    assert summary["counts"]["PENDING_PAYMENT"] == 0
    assert summary["amounts"]["ALL"] == "396.00"
    assert summary["amounts"]["PAID"] == "198.00"
    assert summary["amounts"]["COMPLETED"] == "99.00"
    assert summary["paid_amount"] == "297.00"


def test_summary_empty_user(auth_client):
    response = auth_client.get("/api/v1/users/me/orders/summary/")

    assert response.status_code == 200
    assert response.data["counts"]["ALL"] == 0
    assert response.data["amounts"]["ALL"] == "0.00"
    assert response.data["paid_amount"] == "0.00"


def test_summary_api_only_counts_own_orders(
    auth_client, user, other_user, address, other_address, sku
):
    build_order(user, address, sku, status=Order.Status.PAID)
    build_order(other_user, other_address, sku, status=Order.Status.PAID, quantity=2)

    response = auth_client.get("/api/v1/users/me/orders/summary/")

    assert response.status_code == 200
    assert response.data["counts"]["ALL"] == 1
    assert response.data["paid_amount"] == "99.00"
