from datetime import timedelta

from django.utils import timezone

from apps.support.models import SupportConversation, SupportMessage

CONVERSATION_URL = "/api/v1/support/conversations/"
QUEUE_URL = "/api/v1/admin/support/conversations/"
ASSIGN_URL = "/api/v1/admin/support/conversations/{public_id}/assign/"
CLOSE_URL = "/api/v1/admin/support/conversations/{public_id}/close/"


def test_queue_ordered_by_last_message_time(admin_client, auth_client, other_client):
    auth_client.post(CONVERSATION_URL, {}, format="json")
    other_client.post(CONVERSATION_URL, {}, format="json")
    now = timezone.now()
    SupportConversation.objects.filter(user__username="support_customer").update(
        last_message_at=now
    )
    SupportConversation.objects.filter(user__username="support_other").update(
        last_message_at=now - timedelta(minutes=10)
    )

    response = admin_client.get(QUEUE_URL)

    assert response.status_code == 200
    results = response.json()["results"]
    assert [item["user"]["username"] for item in results] == [
        "support_other",
        "support_customer",
    ]
    assert results[0]["status"] == SupportConversation.Status.WAITING


def test_queue_payload_contains_user_and_order(admin_client, auth_client, order):
    auth_client.post(CONVERSATION_URL, {"order_no": order.order_no}, format="json")

    body = admin_client.get(QUEUE_URL).json()["results"][0]

    assert body["user"]["nickname"] == "王小明"
    assert "phone" not in body["user"]
    assert body["order"]["order_no"] == order.order_no
    assert body["order"]["status_text"] == "已支付"


def test_queue_status_filter(admin_client, auth_client, user):
    created = auth_client.post(CONVERSATION_URL, {}, format="json")
    SupportConversation.objects.filter(public_id=created.json()["public_id"]).update(
        status=SupportConversation.Status.CLOSED
    )

    default_queue = admin_client.get(QUEUE_URL).json()
    all_queue = admin_client.get(QUEUE_URL, {"status": "ALL"}).json()

    assert default_queue["count"] == 0
    assert all_queue["count"] == 1


def test_assign_activates_conversation(admin_client, auth_client, support_client, support_user):
    created = auth_client.post(CONVERSATION_URL, {}, format="json")
    public_id = created.json()["public_id"]

    response = support_client.post(ASSIGN_URL.format(public_id=public_id))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == SupportConversation.Status.ACTIVE
    assert body["agent_name"] == support_user.nickname
    conversation = SupportConversation.objects.get(public_id=public_id)
    assert conversation.agent_id == support_user.pk


def test_concurrent_assign_only_one_wins(
    auth_client, support_client, other_support_client, support_user
):
    created = auth_client.post(CONVERSATION_URL, {}, format="json")
    public_id = created.json()["public_id"]

    first = support_client.post(ASSIGN_URL.format(public_id=public_id))
    second = other_support_client.post(ASSIGN_URL.format(public_id=public_id))
    repeated = support_client.post(ASSIGN_URL.format(public_id=public_id))

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "SUPPORT_CONVERSATION_TAKEN"
    assert repeated.status_code == 200
    assert SupportConversation.objects.get(public_id=public_id).agent_id == support_user.pk


def test_assign_closed_conversation_conflicts(auth_client, support_client, user):
    created = auth_client.post(CONVERSATION_URL, {}, format="json")
    public_id = created.json()["public_id"]
    SupportConversation.objects.filter(public_id=public_id).update(
        status=SupportConversation.Status.CLOSED
    )

    response = support_client.post(ASSIGN_URL.format(public_id=public_id))

    assert response.status_code == 409
    assert response.json()["code"] == "SUPPORT_CONVERSATION_CLOSED"


def test_close_writes_system_message_and_is_idempotent(auth_client, support_client, user):
    created = auth_client.post(CONVERSATION_URL, {}, format="json")
    public_id = created.json()["public_id"]
    support_client.post(ASSIGN_URL.format(public_id=public_id))

    first = support_client.post(CLOSE_URL.format(public_id=public_id))
    second = support_client.post(CLOSE_URL.format(public_id=public_id))

    assert first.status_code == 200
    assert first.json()["status"] == SupportConversation.Status.CLOSED
    assert first.json()["closed_at"] is not None
    assert second.status_code == 200
    conversation = SupportConversation.objects.get(public_id=public_id)
    system_messages = conversation.messages.filter(sender_role=SupportMessage.SenderRole.SYSTEM)
    assert system_messages.count() == 1
    assert "已结束" in system_messages.first().content


def test_customer_cannot_access_admin_queue(auth_client):
    response = auth_client.get(QUEUE_URL)

    assert response.status_code == 403
    assert response.json()["code"] == "COMMON_PERMISSION_DENIED"


def test_admin_queue_supports_keyword_filter(admin_client, auth_client, order):
    auth_client.post(CONVERSATION_URL, {"order_no": order.order_no}, format="json")

    matched = admin_client.get(QUEUE_URL, {"keyword": order.order_no}).json()
    missed = admin_client.get(QUEUE_URL, {"keyword": "不存在的订单"}).json()

    assert matched["count"] == 1
    assert missed["count"] == 0
