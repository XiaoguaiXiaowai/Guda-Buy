"""I11 安全验收：未授权、横纵向越权、注入、上传伪装与信息泄露。"""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.cache import caches
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import Address, User
from apps.catalog.models import Category, Product, Sku
from apps.orders.models import Order, OrderItem
from apps.reviews.models import Review

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    caches["default"].clear()
    yield
    caches["default"].clear()


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def buyer(db):
    return User.objects.create_user(
        username="sec_buyer", email="sec_buyer@example.com", password="Passw0rd123"
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="sec_other", email="sec_other@example.com", password="Passw0rd123"
    )


@pytest.fixture
def operator(db):
    group, _ = Group.objects.get_or_create(name="operator")
    user = User.objects.create_user(
        username="sec_operator", email="sec_operator@example.com", password="Passw0rd123"
    )
    user.groups.add(group)
    return user


@pytest.fixture
def support_user(db):
    group, _ = Group.objects.get_or_create(name="support")
    user = User.objects.create_user(
        username="sec_support", email="sec_support@example.com", password="Passw0rd123"
    )
    user.groups.add(group)
    return user


@pytest.fixture
def auth_client(buyer):
    client = APIClient()
    client.force_authenticate(user=buyer)
    return client


@pytest.fixture
def other_client(other_user):
    client = APIClient()
    client.force_authenticate(user=other_user)
    return client


@pytest.fixture
def operator_client(operator):
    client = APIClient()
    client.force_authenticate(user=operator)
    return client


@pytest.fixture
def category(db):
    return Category.objects.create(name="女装", sort_weight=10)


@pytest.fixture
def product(category):
    return Product.objects.create(
        category=category,
        name="安全测试连衣裙",
        status=Product.Status.ON_SALE,
        price_min=Decimal("99.00"),
        price_max=Decimal("99.00"),
    )


@pytest.fixture
def sku(product):
    return Sku.objects.create(
        product=product,
        sku_code="SEC-DRESS-001",
        spec_text="米白 / M",
        specs={"颜色": "米白", "尺码": "M"},
        sale_price=Decimal("99.00"),
        stock=10,
        stock_capacity=100,
    )


@pytest.fixture
def address(buyer):
    address = Address(
        user=buyer,
        receiver_name="张三",
        province="浙江省",
        city="杭州市",
        district="西湖区",
        detail="文三路 100 号",
        postal_code="310012",
        is_default=True,
    )
    address.set_phone("13800138000")
    address.save()
    return address


def build_order(user, address, sku, *, status=Order.Status.COMPLETED):
    amount = sku.sale_price
    now = timezone.now()
    order = Order.objects.create(
        order_no="GD" + uuid.uuid4().hex[:18].upper(),
        user=user,
        status=status,
        items_amount=amount,
        discount_amount=Decimal("0.00"),
        shipping_amount=Decimal("0.00"),
        payable_amount=amount,
        address_snapshot={"receiver_name": address.receiver_name, "phone": address.phone},
        address_public_id=address.public_id,
        pay_expires_at=now + timedelta(minutes=30),
        shipped_at=now - timedelta(days=2) if status != Order.Status.PENDING_PAYMENT else None,
        completed_at=now - timedelta(days=1) if status == Order.Status.COMPLETED else None,
        idempotency_request_hash="",
    )
    OrderItem.objects.create(
        order=order,
        sku=sku,
        product_name=sku.product.name,
        sku_spec=sku.spec_text,
        main_image=sku.product.main_image,
        unit_price=amount,
        quantity=1,
        item_amount=amount,
    )
    return order


@pytest.fixture
def order(buyer, address, sku):
    return build_order(buyer, address, sku)


@pytest.fixture
def review(buyer, order, sku):
    return Review.objects.create(
        order=order,
        user=buyer,
        product=sku.product,
        sku=sku,
        rating=5,
        content="安全测试用评价内容",
        status=Review.Status.PENDING,
    )


def test_protected_endpoints_require_authentication(client):
    for path in [
        "/api/v1/orders/",
        "/api/v1/users/me/",
        "/api/v1/users/me/addresses/",
        "/api/v1/notifications/",
        "/api/v1/cart/",
        "/api/v1/support/conversations/",
    ]:
        assert client.get(path).status_code == 401, path


def test_horizontal_order_detail_isolation(auth_client, other_client, order):
    own = auth_client.get(f"/api/v1/orders/{order.order_no}/")
    assert own.status_code == 200
    assert own.json()["order_no"] == order.order_no

    leaked = other_client.get(f"/api/v1/orders/{order.order_no}/")
    assert leaked.status_code == 404
    assert "Traceback" not in leaked.content.decode()


def test_horizontal_cancel_and_confirm_blocked(other_client, order):
    assert other_client.post(f"/api/v1/orders/{order.order_no}/cancel/").status_code == 404
    assert other_client.post(f"/api/v1/orders/{order.order_no}/confirm/").status_code == 404
    order.refresh_from_db()
    assert order.status == Order.Status.COMPLETED


def test_horizontal_address_update_blocked(auth_client, other_client, address):
    own = other_client.get("/api/v1/users/me/addresses/")
    assert own.status_code == 200
    own_body = own.json()
    items = own_body if isinstance(own_body, list) else own_body.get("results", [])
    assert all(item["public_id"] != address.public_id for item in items)

    payload = {
        "receiver_name": "被篡改",
        "phone": "13900139000",
        "province": "浙江省",
        "city": "杭州市",
        "district": "西湖区",
        "detail": "被篡改地址",
        "postal_code": "310012",
    }
    assert other_client.get(f"/api/v1/users/me/addresses/{address.public_id}/").status_code == 404
    assert (
        other_client.put(
            f"/api/v1/users/me/addresses/{address.public_id}/", payload, format="json"
        ).status_code
        == 404
    )
    assert (
        other_client.delete(f"/api/v1/users/me/addresses/{address.public_id}/").status_code
        == 404
    )
    address.refresh_from_db()
    assert address.receiver_name == "张三"
    assert address.phone == "13800138000"


def test_horizontal_conversation_blocked(auth_client, other_client, order):
    created = auth_client.post(
        "/api/v1/support/conversations/", {"order_no": order.order_no}, format="json"
    )
    assert created.status_code == 201
    conversation_id = created.json()["public_id"]

    assert other_client.get(
        f"/api/v1/support/conversations/{conversation_id}/messages/"
    ).status_code == 404


def test_member_cannot_use_admin_endpoints(auth_client, order, review, sku):
    assert auth_client.get("/api/v1/admin/orders/").status_code == 403
    assert auth_client.post(
        f"/api/v1/admin/orders/{order.order_no}/ship/", {"tracking_no": "SF1"}, format="json"
    ).status_code == 403
    assert auth_client.get("/api/v1/admin/reviews/").status_code == 403
    assert auth_client.post(
        f"/api/v1/admin/reviews/{review.public_id}/approve/", {}, format="json"
    ).status_code == 403
    assert auth_client.get("/api/v1/admin/support/conversations/").status_code == 403
    assert auth_client.post(
        f"/api/v1/admin/skus/{sku.public_id}/stock/", {}, format="json"
    ).status_code == 403


def test_invalid_and_tampered_token_rejected(buyer, client):
    client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
    assert client.get("/api/v1/orders/").status_code == 401

    token = AccessToken.for_user(buyer)
    token.set_exp(from_time=timezone.now() - timedelta(hours=3), lifetime=timedelta(minutes=30))
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    response = client.get("/api/v1/orders/")
    assert response.status_code == 401
    assert "Traceback" not in response.content.decode()


@pytest.mark.parametrize(
    "search",
    ["' OR 1=1 --", "%27%20OR%201=1--", "<script>alert(1)</script>"],
)
def test_search_injection_returns_safe_json(client, search):
    response = client.get("/api/v1/products/", {"search": search})
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/json")
    body = response.json()
    items = body.get("results", [])
    assert items == []
    assert "<script>" not in response.content.decode()


def test_ordering_injection_is_ignored_or_rejected(client):
    response = client.get(
        "/api/v1/products/", {"ordering": "price_min;DROP TABLE catalog_product;--"}
    )
    assert response.status_code in (200, 400)
    assert response["Content-Type"].startswith("application/json")
    assert "OperationalError" not in response.content.decode()


def test_review_image_disguise_rejected(auth_client, review):
    payload = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 200
    disguised = SimpleUploadedFile("evil.jpg", payload, content_type="image/jpeg")
    response = auth_client.post(
        f"/api/v1/reviews/{review.public_id}/images/", {"image": disguised}, format="multipart"
    )
    assert response.status_code == 400
    assert "Traceback" not in response.content.decode()


def test_review_image_oversize_rejected(auth_client, review):
    oversized = SimpleUploadedFile(
        "big.jpg", b"\xff\xd8\xff" + b"0" * (6 * 1024 * 1024), content_type="image/jpeg"
    )
    response = auth_client.post(
        f"/api/v1/reviews/{review.public_id}/images/", {"image": oversized}, format="multipart"
    )
    assert response.status_code == 400


def test_error_response_does_not_leak_internals(other_client):
    response = other_client.get("/api/v1/orders/GD000000000000000000/")
    assert response.status_code == 404
    body = response.content.decode()
    for marker in ("Traceback", "SELECT", "guda_dev", "site-packages", "mysql"):
        assert marker not in body
    assert response["Content-Type"].startswith("application/json")


def test_order_create_requires_idempotency_key(auth_client, address, sku):
    response = auth_client.post(
        "/api/v1/orders/",
        {"cart_item_public_ids": [], "address_public_id": address.public_id},
        format="json",
    )
    assert response.status_code in (400, 422)
    assert "Traceback" not in response.content.decode()
