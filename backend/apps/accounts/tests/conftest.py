import pytest
from django.core.cache import caches
from django.core import mail
from rest_framework.test import APIClient

from apps.accounts.models import User


@pytest.fixture(autouse=True)
def clear_state():
    for alias in caches:
        caches[alias].clear()
    mail.outbox.clear()
    yield


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="guda_user",
        email="guda@example.com",
        password="Passw0rd123",
    )


@pytest.fixture
def auth_client(client, user):
    client.force_authenticate(user=user)
    return client
