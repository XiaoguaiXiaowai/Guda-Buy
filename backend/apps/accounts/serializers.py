"""账号模块入参校验与出参序列化。"""

import re

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.models import Address

User = get_user_model()

USERNAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,19}$")
PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")


class EmailCodeRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    username = serializers.CharField(max_length=20)
    password = serializers.CharField(max_length=64, trim_whitespace=False)
    email_code = serializers.CharField(max_length=6, min_length=6)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate_username(self, value: str) -> str:
        value = value.strip()
        if not USERNAME_PATTERN.match(value):
            raise serializers.ValidationError(
                "用户名需 3–20 位，以字母开头，仅含字母、数字、下划线"
            )
        return value

    def validate_password(self, value: str) -> str:
        if not 8 <= len(value) <= 64:
            raise serializers.ValidationError("密码长度需为 8–64 位")
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise serializers.ValidationError("密码需同时包含字母与数字")
        return value

    def validate_email_code(self, value: str) -> str:
        value = value.strip()
        if not value.isdigit():
            raise serializers.ValidationError("验证码为 6 位数字")
        return value


class LoginSerializer(serializers.Serializer):
    account = serializers.CharField(max_length=254)
    password = serializers.CharField(max_length=64, trim_whitespace=False)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200)
    new_password = serializers.CharField(max_length=64, trim_whitespace=False)

    def validate_new_password(self, value: str) -> str:
        if not 8 <= len(value) <= 64:
            raise serializers.ValidationError("密码长度需为 8–64 位")
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise serializers.ValidationError("密码需同时包含字母与数字")
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    gender_label = serializers.CharField(source="get_gender_display", read_only=True)

    class Meta:
        model = User
        fields = [
            "public_id",
            "username",
            "email",
            "nickname",
            "gender",
            "gender_label",
            "birthday",
            "avatar",
            "created_at",
        ]
        read_only_fields = ["public_id", "username", "email", "created_at"]

    def get_avatar(self, obj) -> str | None:
        if not obj.avatar:
            return None
        request = self.context.get("request")
        url = obj.avatar if obj.avatar.startswith(("http://", "https://", "/")) else None
        from django.conf import settings

        if url is None:
            url = f"{settings.MEDIA_URL.rstrip('/')}/{obj.avatar.lstrip('/')}"
        return request.build_absolute_uri(url) if request else url


class ProfileUpdateSerializer(serializers.Serializer):
    nickname = serializers.CharField(max_length=30, required=False, allow_blank=False)
    gender = serializers.ChoiceField(choices=User.Gender.choices, required=False)
    birthday = serializers.DateField(required=False, allow_null=True)

    def validate_nickname(self, value: str) -> str:
        value = value.strip()
        if not re.match(r"^[\w\u4e00-\u9fa5]{1,30}$", value):
            raise serializers.ValidationError("昵称需 1–30 位，仅支持中文、字母、数字、下划线")
        return value


class AvatarUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class AddressSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(max_length=11)

    class Meta:
        model = Address
        fields = [
            "public_id",
            "receiver_name",
            "phone",
            "province",
            "city",
            "district",
            "detail",
            "postal_code",
            "is_default",
        ]
        read_only_fields = ["public_id"]

    def validate_receiver_name(self, value: str) -> str:
        value = value.strip()
        if not re.match(r"^[\u4e00-\u9fa5A-Za-z ]{2,20}$", value):
            raise serializers.ValidationError("收货人需 2–20 位中文或字母")
        return value

    def validate_phone(self, value: str) -> str:
        value = value.strip()
        if not PHONE_PATTERN.match(value):
            raise serializers.ValidationError("请输入正确的中国大陆手机号")
        return value

    def validate_postal_code(self, value: str) -> str:
        value = (value or "").strip()
        if value and not re.match(r"^\d{6}$", value):
            raise serializers.ValidationError("邮编需为 6 位数字")
        return value
