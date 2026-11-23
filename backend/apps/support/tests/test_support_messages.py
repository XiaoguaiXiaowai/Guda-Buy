from apps.support.models import SupportConversation

CONVERSATION_URL = "/api/v1/support/conversations/"
MESSAGES_URL = "/api/v1/support/conversations/{public_id}/messages/"
ASSIGN_URL = "/api/v1/admin/support/conversations/{public_id}/assign/"
CLOSE_URL = "/api/v1/admin/support/conversations/{public_id}/close/"


def _conversation(user) -> SupportConversation:
    return SupportConversation.objects.get(user=user)


def test_agent_cannot_reply_before_assign(auth_client, support_client, user):
    auth_client.post(CONVERSATION_URL, {}, format="json")
    public_id = _conversation(user).public_id

    response = support_client.post(
        MESSAGES_URL.format(public_id=public_id),
        {"content": "你好，有什么可以帮你？"},
        format="json",
    )

    assert response.status_code == 422
    assert response.json()["code"] == "SUPPORT_NO_ACTIVE_AGENT"


def test_support_can_read_before_assign(auth_client, support_client, user):
    auth_client.post(CONVERSATION_URL, {}, format="json")
    public_id = _conversation(user).public_id
    auth_client.post(
        MESSAGES_URL.format(public_id=public_id), {"content": "请问什么时候发货？"}, format="json"
    )

    response = support_client.get(MESSAGES_URL.format(public_id=public_id))

    assert response.status_code == 200
    assert response.json()["messages"][0]["content"] == "请问什么时候发货？"


def test_two_way_messages_and_incremental_pull(auth_client, support_client, user):
    auth_client.post(CONVERSATION_URL, {}, format="json")
    public_id = _conversation(user).public_id
    support_client.post(ASSIGN_URL.format(public_id=public_id))

    first = auth_client.post(
        MESSAGES_URL.format(public_id=public_id), {"content": "你好，我想咨询订单"}, format="json"
    )
    support_client.post(
        MESSAGES_URL.format(public_id=public_id), {"content": "你好，请讲"}, format="json"
    )
    auth_client.post(
        MESSAGES_URL.format(public_id=public_id), {"content": "什么时候能发货？"}, format="json"
    )
    support_client.post(
        MESSAGES_URL.format(public_id=public_id), {"content": "今天下午安排发货"}, format="json"
    )

    history = auth_client.get(MESSAGES_URL.format(public_id=public_id)).json()
    assert [item["content"] for item in history["messages"]] == [
        "你好，我想咨询订单",
        "你好，请讲",
        "什么时候能发货？",
        "今天下午安排发货",
    ]
    assert [item["sender_role"] for item in history["messages"]] == [
        "CUSTOMER",
        "AGENT",
        "CUSTOMER",
        "AGENT",
    ]

    anchor = first.json()["public_id"]
    incremental = auth_client.get(
        MESSAGES_URL.format(public_id=public_id), {"after": anchor}
    ).json()
    assert [item["content"] for item in incremental["messages"]] == [
        "你好，请讲",
        "什么时候能发货？",
        "今天下午安排发货",
    ]
    assert incremental["next_after"] == incremental["messages"][-1]["public_id"]

    empty = auth_client.get(
        MESSAGES_URL.format(public_id=public_id), {"after": incremental["next_after"]}
    ).json()
    assert empty["messages"] == []
    assert empty["next_after"] == ""


def test_message_content_validation(auth_client, user):
    auth_client.post(CONVERSATION_URL, {}, format="json")
    public_id = _conversation(user).public_id
    url = MESSAGES_URL.format(public_id=public_id)

    assert auth_client.post(url, {"content": "   "}, format="json").status_code == 400
    html = auth_client.post(url, {"content": "<script>alert(1)</script>"}, format="json")
    assert html.status_code == 400
    assert html.json()["code"] == "COMMON_VALIDATION_ERROR"
    too_long = auth_client.post(url, {"content": "字" * 1001}, format="json")
    assert too_long.status_code == 400


def test_closed_conversation_is_read_only(auth_client, support_client, user):
    auth_client.post(CONVERSATION_URL, {}, format="json")
    public_id = _conversation(user).public_id
    support_client.post(ASSIGN_URL.format(public_id=public_id))
    close = support_client.post(CLOSE_URL.format(public_id=public_id))
    assert close.status_code == 200

    customer_reply = auth_client.post(
        MESSAGES_URL.format(public_id=public_id), {"content": "还想再问一句"}, format="json"
    )
    agent_reply = support_client.post(
        MESSAGES_URL.format(public_id=public_id), {"content": "会话已结束"}, format="json"
    )

    assert customer_reply.status_code == 409
    assert customer_reply.json()["code"] == "SUPPORT_CONVERSATION_CLOSED"
    assert agent_reply.status_code == 409
    assert agent_reply.json()["code"] == "SUPPORT_CONVERSATION_CLOSED"


def test_other_user_cannot_access_conversation(auth_client, other_client, user):
    created = auth_client.post(CONVERSATION_URL, {}, format="json")
    public_id = created.json()["public_id"]
    auth_client.post(
        MESSAGES_URL.format(public_id=public_id), {"content": "我的私密咨询"}, format="json"
    )

    read = other_client.get(MESSAGES_URL.format(public_id=public_id))
    write = other_client.post(
        MESSAGES_URL.format(public_id=public_id), {"content": "越权消息"}, format="json"
    )

    assert read.status_code == 404
    assert write.status_code == 404
    assert read.json()["code"] == "SUPPORT_NOT_PARTICIPANT"


def test_invalid_after_anchor_returns_400(auth_client, user):
    auth_client.post(CONVERSATION_URL, {}, format="json")
    public_id = _conversation(user).public_id

    response = auth_client.get(MESSAGES_URL.format(public_id=public_id), {"after": "not-a-message"})

    assert response.status_code == 400
    assert response.json()["code"] == "COMMON_VALIDATION_ERROR"
