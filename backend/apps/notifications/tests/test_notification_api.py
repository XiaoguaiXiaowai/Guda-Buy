"""站内消息接口：列表筛选、未读数、已读幂等、全部已读与越权。"""

from apps.notifications.models import Notification
from apps.notifications.tests.conftest import make_notification


def test_list_paginates_and_filters_by_type(auth_client, user):
    make_notification(user, title="支付消息", notification_type=Notification.Type.ORDER_PAID)
    make_notification(user, title="系统消息", notification_type=Notification.Type.SYSTEM)

    response = auth_client.get("/api/v1/notifications/")
    assert response.status_code == 200
    assert response.data["count"] == 2
    assert [item["title"] for item in response.data["results"]] == ["系统消息", "支付消息"]

    filtered = auth_client.get("/api/v1/notifications/", {"type": "ORDER_PAID"})
    assert filtered.status_code == 200
    assert filtered.data["count"] == 1
    assert filtered.data["results"][0]["type"] == "ORDER_PAID"
    assert filtered.data["results"][0]["type_text"] == "支付成功"


def test_list_only_returns_own_messages(auth_client, user, other_user):
    make_notification(user, title="我的消息")
    make_notification(other_user, title="他人消息")

    response = auth_client.get("/api/v1/notifications/")

    assert response.data["count"] == 1
    assert response.data["results"][0]["title"] == "我的消息"


def test_entering_list_does_not_clear_unread(auth_client, user):
    make_notification(user)
    make_notification(user)

    auth_client.get("/api/v1/notifications/")
    response = auth_client.get("/api/v1/notifications/unread-count/")

    assert response.status_code == 200
    assert response.data["unread_count"] == 2


def test_mark_read_is_idempotent_and_never_negative(auth_client, user):
    notification = make_notification(user)
    make_notification(user)

    first = auth_client.post(f"/api/v1/notifications/{notification.public_id}/read/")
    assert first.status_code == 200
    assert first.data["is_read"] is True
    assert first.data["unread_count"] == 1

    second = auth_client.post(f"/api/v1/notifications/{notification.public_id}/read/")
    assert second.status_code == 200
    assert second.data["is_read"] is True
    assert second.data["unread_count"] == 1


def test_mark_read_cross_user_returns_404(auth_client, other_user):
    notification = make_notification(other_user)

    response = auth_client.post(f"/api/v1/notifications/{notification.public_id}/read/")

    assert response.status_code == 404
    assert response.data["code"] == "NOTIFY_NOT_FOUND"
    notification.refresh_from_db()
    assert notification.is_read is False


def test_read_all_clears_unread(auth_client, user, other_user):
    make_notification(user)
    make_notification(user)
    foreign = make_notification(other_user)

    response = auth_client.post("/api/v1/notifications/read-all/")

    assert response.status_code == 200
    assert response.data == {"updated": 2, "unread_count": 0}
    assert auth_client.get("/api/v1/notifications/unread-count/").data["unread_count"] == 0
    foreign.refresh_from_db()
    assert foreign.is_read is False


def test_requires_authentication(client):
    response = client.get("/api/v1/notifications/")

    assert response.status_code in (401, 403)
