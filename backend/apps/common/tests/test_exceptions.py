import pytest
from django.test import override_settings
from rest_framework.test import APIClient

ENVELOPE_KEYS = {"code", "message", "detail", "request_id", "timestamp"}


@pytest.fixture
def client():
    return APIClient()


@override_settings(ROOT_URLCONF="apps.common.tests.test_urls")
@pytest.mark.parametrize(
    ("path", "expected_status", "expected_code"),
    [
        ("/exc/400/", 400, "COMMON_VALIDATION_ERROR"),
        ("/exc/401/", 401, "AUTH_TOKEN_INVALID"),
        ("/exc/403/", 403, "COMMON_PERMISSION_DENIED"),
        ("/exc/404/", 404, "COMMON_NOT_FOUND"),
        ("/exc/500/", 500, "COMMON_INTERNAL_ERROR"),
    ],
)
def test_drf_exception_envelope(client, path, expected_status, expected_code):
    response = client.get(path)

    assert response.status_code == expected_status
    payload = response.json()
    assert ENVELOPE_KEYS == set(payload)
    assert payload["code"] == expected_code
    assert payload["request_id"]
    assert response["X-Request-ID"] == payload["request_id"]


@override_settings(ROOT_URLCONF="apps.common.tests.test_urls")
def test_validation_detail_contains_fields(client):
    payload = client.get("/exc/400/").json()

    assert payload["detail"]["fields"]["email"][0] == "邮箱格式不正确"


@override_settings(ROOT_URLCONF="apps.common.tests.test_urls")
def test_internal_error_does_not_leak_stack(client):
    response = client.get("/exc/500/")
    body = response.content.decode()

    assert response.status_code == 500
    assert "数据库连接串泄露示例" not in body
    assert "Traceback" not in body
    assert response.json()["message"] == "服务内部错误"


@override_settings(ROOT_URLCONF="apps.common.tests.test_urls")
def test_business_error_keeps_business_code(client):
    response = client.get("/exc/business/")
    payload = response.json()

    assert response.status_code == 422
    assert payload["code"] == "CART_STOCK_NOT_ENOUGH"
    assert payload["detail"] == {"available": 2}


def test_unknown_route_returns_404_envelope(client):
    response = client.get("/api/v1/not-exist/")

    assert response.status_code == 404
    payload = response.json()
    assert payload["code"] == "COMMON_NOT_FOUND"
    assert response["X-Request-ID"] == payload["request_id"]


def test_request_id_is_propagated_when_provided(client):
    response = client.get("/healthz/", HTTP_X_REQUEST_ID="req-test-1234")

    assert response["X-Request-ID"] == "req-test-1234"
