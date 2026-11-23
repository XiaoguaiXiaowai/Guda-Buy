"""后台券管理：创建、修改、列表与权限。"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.coupons.models import Coupon, CouponScope
from apps.coupons.tests.conftest import add_scope, make_coupon, make_user_coupon
from apps.orders.tests.conftest import build_order


def _payload(**overrides):
    now = timezone.now()
    data = {
        "name": "开业满减券",
        "coupon_type": "FIXED",
        "value": "20.00",
        "min_amount": "100.00",
        "total_quantity": 100,
        "per_user_limit": 1,
        "scope_type": "ALL",
        "valid_from": (now - timedelta(hours=1)).isoformat(),
        "valid_to": (now + timedelta(days=7)).isoformat(),
        "status": "ACTIVE",
    }
    data.update(overrides)
    return data


def test_admin_create_coupon(operator_client, category):
    response = operator_client.post(
        "/api/v1/admin/coupons/",
        _payload(
            scope_type="CATEGORY",
            scope_category_public_ids=[category.public_id],
        ),
        format="json",
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "开业满减券"
    assert payload["status"] == "ACTIVE"
    assert len(payload["scope_categories"]) == 1
    coupon = Coupon.objects.get(public_id=payload["public_id"])
    assert coupon.claimed_quantity == 0
    assert coupon.scopes.count() == 1


def test_admin_create_requires_coupon_permission(auth_client):
    response = auth_client.post("/api/v1/admin/coupons/", _payload(), format="json")
    assert response.status_code == 403
    assert response.json()["code"] == "COMMON_PERMISSION_DENIED"


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"coupon_type": "FIXED", "value": "0"}, "value"),
        ({"coupon_type": "DISCOUNT", "value": "1.5"}, "value"),
        ({"valid_to": "2020-01-01T00:00:00+08:00"}, "valid_to"),
        ({"scope_type": "CATEGORY", "scope_category_public_ids": []}, "scope_category_public_ids"),
        ({"scope_type": "PRODUCT", "scope_product_public_ids": []}, "scope_product_public_ids"),
        ({"scope_type": "ALL", "scope_product_public_ids": ["x"]}, "scope_type"),
        ({"total_quantity": 0}, "total_quantity"),
    ],
)
def test_admin_create_validation(operator_client, overrides, field):
    response = operator_client.post("/api/v1/admin/coupons/", _payload(**overrides), format="json")
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "COMMON_VALIDATION_ERROR"
    assert field in body["detail"]["fields"]


def test_admin_create_rejects_unknown_scope(operator_client):
    response = operator_client.post(
        "/api/v1/admin/coupons/",
        _payload(scope_type="CATEGORY", scope_category_public_ids=["not-exists"]),
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == "COMMON_VALIDATION_ERROR"


def test_admin_create_free_shipping_forces_zero_value(operator_client):
    response = operator_client.post(
        "/api/v1/admin/coupons/",
        _payload(coupon_type="FREE_SHIPPING", value=None, min_amount="0"),
        format="json",
    )
    assert response.status_code == 201
    assert Decimal(response.json()["value"]) == Decimal("0.00")


def test_admin_list_shows_claimed_used_and_scope(
    operator_client, user, category, product, address, sku
):
    coupon = make_coupon(scope_type=Coupon.ScopeType.PRODUCT, claimed_quantity=2)
    add_scope(coupon, product=product)
    order = build_order(user, address, sku)
    make_user_coupon(
        user,
        coupon,
        status="USED",
        used_at=timezone.now(),
        order=order,
    )
    make_coupon(name="停止券", status=Coupon.Status.STOPPED)

    response = operator_client.get("/api/v1/admin/coupons/")
    assert response.status_code == 200
    body = response.json()
    rows = body["results"] if "results" in body else body
    assert len(rows) == 2
    target = next(row for row in rows if row["public_id"] == coupon.public_id)
    assert target["claimed_quantity"] == 2
    assert target["used_quantity"] == 1
    assert target["scope_products"][0]["name"] == product.name

    stopped = operator_client.get("/api/v1/admin/coupons/?status=STOPPED").json()
    stopped_rows = stopped["results"] if "results" in stopped else stopped
    assert [row["name"] for row in stopped_rows] == ["停止券"]


def test_admin_list_supports_type_and_keyword(operator_client):
    make_coupon(name="包邮券", coupon_type=Coupon.Type.FREE_SHIPPING, value="0", min_amount="0")
    make_coupon(name="满减券")
    response = operator_client.get("/api/v1/admin/coupons/?coupon_type=FREE_SHIPPING")
    rows = response.json()
    rows = rows["results"] if "results" in rows else rows
    assert [row["name"] for row in rows] == ["包邮券"]

    response = operator_client.get("/api/v1/admin/coupons/?keyword=满减")
    rows = response.json()
    rows = rows["results"] if "results" in rows else rows
    assert [row["name"] for row in rows] == ["满减券"]


def test_admin_update_before_claim(operator_client, category):
    coupon = make_coupon(scope_type=Coupon.ScopeType.CATEGORY)
    add_scope(coupon, category=category)
    response = operator_client.patch(
        f"/api/v1/admin/coupons/{coupon.public_id}/",
        {
            "name": "改名后的券",
            "min_amount": "150.00",
            "status": "DRAFT",
            "scope_type": "ALL",
            "scope_category_public_ids": [],
        },
        format="json",
    )
    assert response.status_code == 200
    coupon.refresh_from_db()
    assert coupon.name == "改名后的券"
    assert coupon.min_amount == Decimal("150.00")
    assert coupon.status == Coupon.Status.DRAFT
    assert coupon.scopes.count() == 0


def test_admin_partial_update_keeps_existing_scopes(operator_client, category):
    coupon = make_coupon(scope_type=Coupon.ScopeType.CATEGORY)
    add_scope(coupon, category=category)
    response = operator_client.patch(
        f"/api/v1/admin/coupons/{coupon.public_id}/", {"name": "只改名字"}, format="json"
    )
    assert response.status_code == 200
    coupon.refresh_from_db()
    assert coupon.name == "只改名字"
    assert coupon.scopes.count() == 1


def test_admin_switch_scope_without_targets_is_rejected(operator_client, category):
    coupon = make_coupon(scope_type=Coupon.ScopeType.CATEGORY)
    add_scope(coupon, category=category)
    response = operator_client.patch(
        f"/api/v1/admin/coupons/{coupon.public_id}/",
        {"scope_type": "PRODUCT"},
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == "COMMON_VALIDATION_ERROR"


def test_admin_update_blocked_after_claim(operator_client):
    coupon = make_coupon(claimed_quantity=1)
    response = operator_client.patch(
        f"/api/v1/admin/coupons/{coupon.public_id}/", {"name": "改不了"}, format="json"
    )
    assert response.status_code == 409
    assert response.json()["code"] == "COUPON_STATUS_CONFLICT"


def test_admin_update_unknown(operator_client):
    response = operator_client.patch(
        "/api/v1/admin/coupons/not-exists/", {"name": "改不了"}, format="json"
    )
    assert response.status_code == 404
    assert response.json()["code"] == "COUPON_NOT_FOUND"


def test_admin_update_invalid_scope_keeps_old_scopes(operator_client, category):
    coupon = make_coupon(scope_type=Coupon.ScopeType.CATEGORY)
    add_scope(coupon, category=category)
    response = operator_client.patch(
        f"/api/v1/admin/coupons/{coupon.public_id}/",
        {"scope_product_public_ids": ["missing"]},
        format="json",
    )
    assert response.status_code == 400
    assert CouponScope.objects.filter(coupon=coupon).count() == 1
