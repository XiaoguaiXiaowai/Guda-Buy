import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.accounts import services
from apps.accounts.models import Address, User
from apps.common.exceptions import BusinessError

pytestmark = pytest.mark.django_db

ME_URL = "/api/v1/users/me/"
AVATAR_URL = "/api/v1/users/me/avatar/"
ADDRESS_URL = "/api/v1/users/me/addresses/"


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color=(20, 120, 220)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_me_requires_authentication(client):
    assert client.get(ME_URL).status_code == 401


def test_get_and_update_profile(auth_client, user):
    response = auth_client.get(ME_URL)
    assert response.status_code == 200
    assert response.json()["public_id"] == user.public_id
    assert "phone" not in response.json()

    updated = auth_client.patch(
        ME_URL,
        {"nickname": "古达小买家", "gender": "FEMALE", "birthday": "1998-05-20"},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["nickname"] == "古达小买家"
    assert updated.json()["gender"] == "FEMALE"
    assert updated.json()["birthday"] == "1998-05-20"


def test_update_profile_rejects_invalid_nickname(auth_client):
    response = auth_client.patch(ME_URL, {"nickname": "  "}, format="json")
    assert response.status_code == 400


def test_upload_avatar_validates_type_and_stores_file(auth_client, user, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path

    bad = auth_client.post(
        AVATAR_URL,
        {"file": SimpleUploadedFile("shell.exe", b"MZ-not-an-image")},
        format="multipart",
    )
    assert bad.status_code == 400
    assert bad.json()["code"] == "COMMON_VALIDATION_ERROR"

    good = auth_client.post(
        AVATAR_URL,
        {"file": SimpleUploadedFile("avatar.png", _png_bytes(), content_type="image/png")},
        format="multipart",
    )
    assert good.status_code == 200
    assert "/media/avatars/" in good.json()["avatar"]

    user.refresh_from_db()
    assert user.avatar.startswith("avatars/")
    assert (tmp_path / user.avatar).exists()


def test_address_crud_and_default_uniqueness(auth_client, user):
    first = auth_client.post(
        ADDRESS_URL,
        {
            "receiver_name": "张三",
            "phone": "13800138000",
            "province": "广东省",
            "city": "深圳市",
            "district": "南山区",
            "detail": "科技园路 1 号",
            "postal_code": "518000",
            "is_default": False,
        },
        format="json",
    )
    assert first.status_code == 201
    first_payload = first.json()
    assert first_payload["is_default"] is True  # 首条自动默认
    assert first_payload["phone"] == "13800138000"

    second = auth_client.post(
        ADDRESS_URL,
        {
            "receiver_name": "李四",
            "phone": "13900139000",
            "province": "北京市",
            "city": "北京市",
            "district": "朝阳区",
            "detail": "建国路 88 号",
            "is_default": True,
        },
        format="json",
    )
    assert second.status_code == 201

    listed = auth_client.get(ADDRESS_URL).json()
    assert len(listed) == 2
    assert listed[0]["receiver_name"] == "李四"
    assert sum(1 for item in listed if item["is_default"]) == 1

    detail_url = f"{ADDRESS_URL}{first_payload['public_id']}/"
    updated = auth_client.put(
        detail_url,
        {
            "receiver_name": "张三丰",
            "phone": "13800138000",
            "province": "广东省",
            "city": "深圳市",
            "district": "南山区",
            "detail": "科技园路 2 号",
            "is_default": False,
        },
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["receiver_name"] == "张三丰"

    promoted = auth_client.post(f"{detail_url}default/")
    assert promoted.status_code == 200
    assert promoted.json()["is_default"] is True

    deleted = auth_client.delete(detail_url)
    assert deleted.status_code == 204
    assert Address.objects.filter(user=user).count() == 1


def test_address_phone_is_encrypted_at_rest(auth_client, user):
    auth_client.post(
        ADDRESS_URL,
        {
            "receiver_name": "王五",
            "phone": "13700137000",
            "province": "上海市",
            "city": "上海市",
            "district": "浦东新区",
            "detail": "世纪大道 1 号",
        },
        format="json",
    )
    address = Address.objects.get(user=user)
    assert address.phone_encrypted != "13700137000"
    assert address.phone_hash != "13700137000"
    assert address.phone == "13700137000"


def test_address_limit_20(user):
    payload = {
        "receiver_name": "测试",
        "phone": "13600136000",
        "province": "浙江省",
        "city": "杭州市",
        "district": "西湖区",
        "detail": "文三路 1 号",
    }
    for _ in range(20):
        services.create_address(user, dict(payload))

    with pytest.raises(BusinessError) as exc:
        services.create_address(user, dict(payload))
    assert exc.value.code == "USER_ADDRESS_LIMIT"


def test_cannot_access_other_users_address(auth_client, user):
    other = User.objects.create_user(
        username="other_user", email="other@guda.test", password="Passw0rd123"
    )
    address = services.create_address(
        other,
        {
            "receiver_name": "赵六",
            "phone": "13500135000",
            "province": "江苏省",
            "city": "南京市",
            "district": "玄武区",
            "detail": "中山路 1 号",
        },
    )

    response = auth_client.get(f"{ADDRESS_URL}{address.public_id}/")
    assert response.status_code == 404


def test_address_validation(auth_client):
    response = auth_client.post(
        ADDRESS_URL,
        {
            "receiver_name": "A",
            "phone": "12345",
            "province": "广东省",
            "city": "深圳市",
            "district": "南山区",
            "detail": "x",
        },
        format="json",
    )
    assert response.status_code == 400


ADDRESS_PAYLOAD = {
    "receiver_name": "测试",
    "phone": "13600136000",
    "province": "浙江省",
    "city": "杭州市",
    "district": "西湖区",
    "detail": "文三路 1 号",
}


def test_update_address_switches_and_keeps_default(user):
    first = services.create_address(user, dict(ADDRESS_PAYLOAD))
    second = services.create_address(user, dict(ADDRESS_PAYLOAD))

    services.update_address(user, second.public_id, {**ADDRESS_PAYLOAD, "is_default": True})
    first.refresh_from_db()
    second.refresh_from_db()
    assert second.is_default is True
    assert first.is_default is False

    # 唯一默认地址不允许被取消，避免出现无默认地址
    services.update_address(user, second.public_id, {**ADDRESS_PAYLOAD, "is_default": False})
    second.refresh_from_db()
    assert second.is_default is True


def test_address_service_returns_404_for_missing(user):
    with pytest.raises(BusinessError):
        services.update_address(user, "missing", dict(ADDRESS_PAYLOAD))
    with pytest.raises(BusinessError):
        services.set_default_address(user, "missing")
    with pytest.raises(BusinessError):
        services.delete_address(user, "missing")


def test_avatar_rejects_wrong_mime_and_oversize(auth_client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path

    wrong_mime = auth_client.post(
        AVATAR_URL,
        {"file": SimpleUploadedFile("avatar.png", _png_bytes(), content_type="image/gif")},
        format="multipart",
    )
    assert wrong_mime.status_code == 400

    too_large = auth_client.post(
        AVATAR_URL,
        {
            "file": SimpleUploadedFile(
                "avatar.png",
                b"0" * (services.AVATAR_MAX_BYTES + 1),
                content_type="image/png",
            )
        },
        format="multipart",
    )
    assert too_large.status_code == 400


def test_avatar_rejects_corrupt_and_oversized_image(auth_client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path

    corrupt = auth_client.post(
        AVATAR_URL,
        {"file": SimpleUploadedFile("avatar.png", b"not-an-image", content_type="image/png")},
        format="multipart",
    )
    assert corrupt.status_code == 400

    buffer = io.BytesIO()
    Image.new("RGB", (services.AVATAR_MAX_SIDE + 1, 2), color=(0, 0, 0)).save(buffer, format="PNG")
    oversized = auth_client.post(
        AVATAR_URL,
        {"file": SimpleUploadedFile("avatar.png", buffer.getvalue(), content_type="image/png")},
        format="multipart",
    )
    assert oversized.status_code == 400


def test_replacing_avatar_removes_previous_file(auth_client, user, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path

    for index in range(2):
        response = auth_client.post(
            AVATAR_URL,
            {
                "file": SimpleUploadedFile(
                    f"avatar{index}.png", _png_bytes(), content_type="image/png"
                )
            },
            format="multipart",
        )
        assert response.status_code == 200

    user.refresh_from_db()
    stored = list((tmp_path / "avatars").iterdir())
    assert len(stored) == 1
    assert stored[0].name == user.avatar.split("/")[-1]
