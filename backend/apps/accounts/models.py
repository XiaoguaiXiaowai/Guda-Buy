"""会员、收货地址模型（架构文档 7.3 accounts_users / accounts_addresses）。"""

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from apps.common.crypto import decrypt_phone, encrypt_phone, hash_phone


def generate_public_id() -> str:
    return uuid.uuid4().hex


class User(AbstractUser):
    """自定义用户：邮箱登录、手机号密文存储、展示资料。"""

    class Gender(models.TextChoices):
        UNKNOWN = "UNKNOWN", "保密"
        MALE = "MALE", "男"
        FEMALE = "FEMALE", "女"

    public_id = models.CharField(
        "对外标识", max_length=32, unique=True, default=generate_public_id, editable=False
    )
    email = models.EmailField("邮箱", max_length=254, unique=True)
    nickname = models.CharField("昵称", max_length=30, blank=True, default="")
    gender = models.CharField(
        "性别", max_length=16, choices=Gender.choices, default=Gender.UNKNOWN
    )
    birthday = models.DateField("生日", null=True, blank=True)
    avatar = models.CharField("头像路径", max_length=255, blank=True, default="")
    phone_encrypted = models.CharField("手机号密文", max_length=128, blank=True, default="")
    phone_hash = models.CharField(
        "手机号检索哈希", max_length=64, unique=True, null=True, blank=True
    )
    last_login_at = models.DateTimeField("最近登录", null=True, blank=True)
    is_deleted = models.BooleanField("是否删除", default=False)
    deleted_at = models.DateTimeField("删除时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "accounts_users"
        verbose_name = "会员"
        verbose_name_plural = "会员"
        permissions = [("change_user_role", "可变更用户角色")]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_public_id()
        if self.email:
            self.email = self.email.strip().lower()
        self.username = (self.username or "").strip()
        if not self.nickname:
            self.nickname = self.username
        super().save(*args, **kwargs)

    @property
    def phone(self) -> str:
        """解密后的手机号，仅用于本人可见场景，禁止写入日志。"""
        return decrypt_phone(self.phone_encrypted)

    def set_phone(self, phone: str) -> None:
        phone = phone.strip()
        self.phone_encrypted = encrypt_phone(phone)
        self.phone_hash = hash_phone(phone)

    def mark_login(self) -> None:
        self.last_login_at = timezone.now()


class Address(models.Model):
    """收货地址：默认地址唯一由 service 在事务内保证。"""

    public_id = models.CharField(
        "对外标识", max_length=32, unique=True, default=generate_public_id, editable=False
    )
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="addresses", verbose_name="所属用户"
    )
    receiver_name = models.CharField("收货人", max_length=20)
    phone_encrypted = models.CharField("收货手机号密文", max_length=128)
    phone_hash = models.CharField("收货手机号哈希", max_length=64)
    province = models.CharField("省", max_length=64)
    city = models.CharField("市", max_length=64)
    district = models.CharField("区/县", max_length=64)
    detail = models.CharField("详细地址", max_length=200)
    postal_code = models.CharField("邮编", max_length=10, blank=True, default="")
    is_default = models.BooleanField("是否默认", default=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "accounts_addresses"
        verbose_name = "收货地址"
        verbose_name_plural = "收货地址"
        ordering = ["-is_default", "-created_at"]
        indexes = [
            models.Index(fields=["user", "is_default"], name="idx_acct_addr_user_default"),
        ]

    def __str__(self) -> str:
        return f"{self.receiver_name} · {self.province}{self.city}{self.district}"

    @property
    def phone(self) -> str:
        return decrypt_phone(self.phone_encrypted)

    def set_phone(self, phone: str) -> None:
        phone = phone.strip()
        self.phone_encrypted = encrypt_phone(phone)
        self.phone_hash = hash_phone(phone)
