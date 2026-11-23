from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import User
from apps.support.models import SupportConversation, SupportMessage
from apps.support.tasks import close_inactive_conversations


def _stale_conversation(user, hours_ago: int = 25, status=SupportConversation.Status.WAITING):
    conversation = SupportConversation.objects.create(user=user, status=status)
    SupportConversation.objects.filter(pk=conversation.pk).update(
        last_message_at=timezone.now() - timedelta(hours=hours_ago)
    )
    conversation.refresh_from_db()
    return conversation


def test_inactive_conversation_is_closed(user, other_user):
    stale = _stale_conversation(user)
    fresh = SupportConversation.objects.create(user=other_user)

    closed = close_inactive_conversations()

    assert closed == 1
    stale.refresh_from_db()
    fresh.refresh_from_db()
    assert stale.status == SupportConversation.Status.CLOSED
    assert stale.closed_at is not None
    assert fresh.status == SupportConversation.Status.WAITING
    message = stale.messages.get(sender_role=SupportMessage.SenderRole.SYSTEM)
    assert "自动关闭" in message.content


def test_batch_limit_caps_processed_conversations(db):
    users = [
        User.objects.create_user(
            username=f"support_batch_{index}",
            email=f"support_batch_{index}@example.com",
            password="Passw0rd123",
        )
        for index in range(3)
    ]
    conversations = [_stale_conversation(item) for item in users]

    closed = close_inactive_conversations(limit=2)

    assert closed == 2
    statuses = list(
        SupportConversation.objects.filter(pk__in=[item.pk for item in conversations]).values_list(
            "status", flat=True
        )
    )
    assert statuses.count(SupportConversation.Status.WAITING) == 1


def test_closed_conversation_is_ignored(user):
    conversation = _stale_conversation(user, status=SupportConversation.Status.CLOSED)

    closed = close_inactive_conversations()

    assert closed == 0
    conversation.refresh_from_db()
    assert conversation.status == SupportConversation.Status.CLOSED
