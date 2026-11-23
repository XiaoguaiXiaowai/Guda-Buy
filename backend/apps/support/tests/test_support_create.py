from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import Address
from apps.orders.models import Order
from apps.support.models import SupportConversation

CONVERSATION_URL = "/api/v1/support/conversations/"


def test_create_conversation_with_order(auth_client, user, order):
    response = auth_client.post(CONVERSATION_URL, {"order_no": order.order_no}, format="json")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == SupportConversation.Status.WAITING
    assert body["order"]["order_no"] == order.order_no
    assert body["agent_name"] == ""
    conversation = SupportConversation.objects.get(public_id=body["public_id"])
    assert conversation.user_id == user.pk
    assert conversation.order_id == order.pk


def test_only_one_open_conversation_per_user(auth_client, user):
    first = auth_client.post(CONVERSATION_URL, {}, format="json")
    second = auth_client.post(CONVERSATION_URL, {}, format="json")

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["public_id"] == first.json()["public_id"]
    assert SupportConversation.objects.filter(user=user).count() == 1


def test_existing_conversation_can_attach_order(auth_client, order):
    created = auth_client.post(CONVERSATION_URL, {}, format="json")

    response = auth_client.post(CONVERSATION_URL, {"order_no": order.order_no}, format="json")

    assert response.status_code == 200
    assert response.json()["public_id"] == created.json()["public_id"]
    assert response.json()["order"]["order_no"] == order.order_no


def test_create_with_foreign_order_returns_not_found(auth_client, other_user, sku):
    other_address = Address.objects.create(
        user=other_user,
        receiver_name="李四",
        province="江苏省",
        city="南京市",
        district="鼓楼区",
        detail="中山路 1 号",
        postal_code="210000",
        is_default=True,
    )
    now = timezone.now()
    other_order = Order.objects.create(
        order_no="GDOTHERORDER00000001",
        user=other_user,
        status=Order.Status.PAID,
        items_amount=sku.sale_price,
        payable_amount=sku.sale_price,
        address_snapshot={"receiver_name": other_address.receiver_name},
        address_public_id=other_address.public_id,
        pay_expires_at=now + timedelta(minutes=30),
        paid_at=now,
        idempotency_request_hash="",
    )

    response = auth_client.post(CONVERSATION_URL, {"order_no": other_order.order_no}, format="json")

    assert response.status_code == 404
    assert response.json()["code"] == "ORDER_NOT_FOUND"
    assert SupportConversation.objects.count() == 0


def test_list_my_conversations(auth_client, order):
    auth_client.post(CONVERSATION_URL, {"order_no": order.order_no}, format="json")

    response = auth_client.get(CONVERSATION_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["order"]["order_no"] == order.order_no


def test_closed_conversation_allows_new_one(auth_client, user):
    created = auth_client.post(CONVERSATION_URL, {}, format="json")
    SupportConversation.objects.filter(public_id=created.json()["public_id"]).update(
        status=SupportConversation.Status.CLOSED
    )

    response = auth_client.post(CONVERSATION_URL, {}, format="json")

    assert response.status_code == 201
    assert response.json()["public_id"] != created.json()["public_id"]
    assert SupportConversation.objects.filter(user=user).count() == 2
