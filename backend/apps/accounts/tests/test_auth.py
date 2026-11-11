import re

import pytest
from django.core import mail
from django.core.cache import caches
from django.test import override_settings

from apps.accounts import services
from apps.accounts.models import User

pytestmark = pytest.mark.django_db

REGISTER_URL = "/api/v1/auth/register/"
LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
EMAIL_CODE_URL = "/api/v1/auth/email-code/"
RESET_REQUEST_URL = "/api/v1/auth/password/reset/"
RESET_CONFIRM_URL = "/api/v1/auth/password/reset/confirm/"


def _code_of(email: str) -> str:
    return caches["security"].get(f"auth:code:register:{email}")


def _register(client, email="new@guda.test", username="new_user", password="Passw0rd123"):
    services.send_email_code(email)
    return client.post(
        REGISTER_URL,
        {
            "email": email,
            "username": username,
            "password": password,
            "email_code": _code_of(email),
        },
        format="json",
    )


def test_send_email_code_limits_resend(client):
    email = "code@guda.test"
    first = client.post(EMAIL_CODE_URL, {"email": email}, format="json")
    second = client.post(EMAIL_CODE_URL, {"email": email}, format="json")

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["code"] == "AUTH_CODE_TOO_FREQUENT"
    assert len(mail.outbox) == 1
    assert re.search(r"\d{6}", mail.outbox[0].body)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.Argon2PasswordHasher"])
def test_register_success_and_password_hashed_with_argon2(client):
    response = _register(client)

    assert response.status_code == 201
    payload = response.json()
    assert payload["access"]
    assert payload["user"]["email"] == "new@guda.test"
    assert response.cookies["refresh"]["httponly"]
    assert response.cookies["refresh"]["path"] == "/api/v1/auth/"

    user = User.objects.get(email="new@guda.test")
    assert user.password.startswith("argon2$")
    assert user.nickname == "new_user"
    assert user.groups.filter(name="customer").exists()


def test_register_rejects_reused_code(client):
    email = "reuse@guda.test"
    services.send_email_code(email)
    code = _code_of(email)
    payload = {
        "email": email,
        "username": "reuse_user",
        "password": "Passw0rd123",
        "email_code": code,
    }

    assert client.post(REGISTER_URL, payload, format="json").status_code == 201
    response = client.post(
        REGISTER_URL,
        {**payload, "username": "reuse_two"},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["code"] == "AUTH_CODE_INVALID"


def test_register_duplicate_email_returns_409(client):
    assert _register(client, email="dup@guda.test", username="first_name").status_code == 201

    caches["security"].set("auth:code:register:dup@guda.test", "123456", timeout=300)
    again = client.post(
        REGISTER_URL,
        {
            "email": "dup@guda.test",
            "username": "second_name",
            "password": "Passw0rd123",
            "email_code": "123456",
        },
        format="json",
    )
    assert again.status_code == 409
    assert again.json()["code"] == "USER_EMAIL_EXISTS"


def test_login_with_email_sets_refresh_cookie(client, user):
    response = client.post(
        LOGIN_URL,
        {"account": "GUDA@example.com", "password": "Passw0rd123"},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["access"]
    assert response.cookies["refresh"]["httponly"]
    user.refresh_from_db()
    assert user.last_login_at is not None


def test_login_lockout_after_five_failures(client, user):
    for _ in range(5):
        response = client.post(
            LOGIN_URL, {"account": user.username, "password": "wrong-pass"}, format="json"
        )
        assert response.status_code == 401
        assert response.json()["code"] == "AUTH_INVALID_CREDENTIALS"

    blocked = client.post(
        LOGIN_URL, {"account": user.username, "password": "Passw0rd123"}, format="json"
    )
    assert blocked.status_code == 423
    assert blocked.json()["code"] == "AUTH_ACCOUNT_LOCKED"


def test_refresh_rotates_and_revokes_old_token(client, user):
    client.post(LOGIN_URL, {"account": user.username, "password": "Passw0rd123"}, format="json")
    old_cookie = client.cookies["refresh"].value

    refreshed = client.post(REFRESH_URL, {}, format="json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
    assert refreshed.status_code == 200
    assert refreshed.json()["access"]
    new_cookie = refreshed.cookies["refresh"].value
    assert new_cookie != old_cookie

    # 旧 Cookie 重放应被黑名单拦截
    client.cookies["refresh"] = old_cookie
    replay = client.post(REFRESH_URL, {}, format="json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
    assert replay.status_code == 401
    assert replay.json()["code"] == "AUTH_REFRESH_REVOKED"


def test_refresh_requires_x_requested_with(client, user):
    client.post(LOGIN_URL, {"account": user.username, "password": "Passw0rd123"}, format="json")
    response = client.post(REFRESH_URL, {}, format="json")
    assert response.status_code == 403


def test_logout_blacklists_refresh_and_clears_cookie(client, user):
    login = client.post(
        LOGIN_URL, {"account": user.username, "password": "Passw0rd123"}, format="json"
    )
    access = login.json()["access"]
    client.cookies["refresh"] = login.cookies["refresh"].value

    response = client.post(
        LOGOUT_URL,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {access}",
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 200
    assert response.cookies["refresh"]["max-age"] == 0


def test_password_reset_revokes_all_refresh_tokens(client, user):
    login = client.post(
        LOGIN_URL, {"account": user.username, "password": "Passw0rd123"}, format="json"
    )
    old_refresh = login.cookies["refresh"].value

    client.post(RESET_REQUEST_URL, {"email": user.email}, format="json")
    body = mail.outbox[-1].body
    token = re.search(r"token=([\w\-]+)", body).group(1)

    confirm = client.post(
        RESET_CONFIRM_URL,
        {"token": token, "new_password": "NewPassw0rd9"},
        format="json",
    )
    assert confirm.status_code == 200

    user.refresh_from_db()
    assert user.check_password("NewPassw0rd9")

    client.cookies["refresh"] = old_refresh
    replay = client.post(REFRESH_URL, {}, format="json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
    assert replay.status_code == 401
    assert replay.json()["code"] == "AUTH_REFRESH_REVOKED"

    reused = client.post(
        RESET_CONFIRM_URL,
        {"token": token, "new_password": "Another123"},
        format="json",
    )
    assert reused.status_code == 400


def test_password_reset_does_not_reveal_unknown_email(client):
    response = client.post(RESET_REQUEST_URL, {"email": "ghost@guda.test"}, format="json")

    assert response.status_code == 200
    assert len(mail.outbox) == 0


def test_register_validates_password_strength(client):
    services.send_email_code("weak@guda.test")
    response = client.post(
        REGISTER_URL,
        {
            "email": "weak@guda.test",
            "username": "weak_user",
            "password": "onlyletters",
            "email_code": _code_of("weak@guda.test"),
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["code"] == "COMMON_VALIDATION_ERROR"
