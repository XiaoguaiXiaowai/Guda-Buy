from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


def test_healthz_returns_ok_when_dependencies_ready(client):
    response = client.get("/healthz/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "redis": "ok"}
    assert response["Cache-Control"] == "no-store"
    assert response["X-Request-ID"]


def test_healthz_returns_503_when_redis_down(client):
    with patch("apps.common.views._check_redis", return_value=False):
        response = client.get("/healthz/")

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "COMMON_SERVICE_UNAVAILABLE"
    assert payload["detail"] == {"db": "ok", "redis": "fail"}


def test_healthz_returns_503_when_db_down(client):
    with patch("apps.common.views._check_database", return_value=False):
        response = client.get("/healthz/")

    assert response.status_code == 503
    assert response.json()["detail"] == {"db": "fail", "redis": "ok"}


def test_api_root_is_public(client):
    response = client.get("/api/v1/")

    assert response.status_code == 200
    assert response.json()["version"] == "v1"
