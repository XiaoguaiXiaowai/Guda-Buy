"""账号领域服务：事务边界与业务规则唯一写入口。"""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.core.cache import caches
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from PIL import Image, UnidentifiedImageError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Address
from apps.common.exceptions import BusinessError

logger = logging.getLogger("guda.accounts")
User = get_user_model()

# 验证码、失败计数等易失数据统一放 security cache（Redis DB3）
cache = caches["security"]

# ---------------------------------------------------------------------------
# 邮箱验证码
# ---------------------------------------------------------------------------
EMAIL_CODE_PURPOSE_REGISTER = "register"


def _code_key(purpose: str, email: str) -> str:
    return f"auth:code:{purpose}:{email.lower()}"


def _code_fail_key(purpose: str, email: str) -> str:
    return f"auth:code_fail:{purpose}:{email.lower()}"


def _code_send_key(email: str) -> str:
    return f"auth:code_send:{email.lower()}"


def _code_daily_key(email: str) -> str:
    return f"auth:code_daily:{email.lower()}"


def _seconds_until_midnight() -> int:
    now = timezone.localtime()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(int((tomorrow - now).total_seconds()), 60)


def send_email_code(email: str, purpose: str = EMAIL_CODE_PURPOSE_REGISTER) -> None:
    """发送 6 位验证码：60 秒重发限制、每日 10 次、5 分钟有效。"""
    email = email.strip().lower()

    if cache.get(_code_send_key(email)):
        raise BusinessError(
            "AUTH_CODE_TOO_FREQUENT", "验证码发送过于频繁，请稍后再试", http_status=429
        )

    sent_today = cache.get(_code_daily_key(email), 0)
    if sent_today >= settings.AUTH_EMAIL_CODE_DAILY_LIMIT:
        raise BusinessError("AUTH_CODE_TOO_FREQUENT", "今日验证码发送次数已达上限", http_status=429)

    code = f"{secrets.randbelow(1_000_000):06d}"
    cache.set(_code_key(purpose, email), code, timeout=settings.AUTH_EMAIL_CODE_TTL_SECONDS)
    cache.delete(_code_fail_key(purpose, email))
    cache.set(_code_send_key(email), 1, timeout=settings.AUTH_EMAIL_CODE_RESEND_SECONDS)
    cache.set(_code_daily_key(email), sent_today + 1, timeout=_seconds_until_midnight())

    send_mail(
        subject="GUDA 商城验证码",
        message=f"您的验证码是 {code}，5 分钟内有效。如非本人操作请忽略本邮件。",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
    if settings.DEBUG:
        logger.info(
            "开发环境邮箱验证码：%s",
            code,
            extra={"action": "send_email_code", "result": "ok"},
        )


def verify_email_code(email: str, code: str, purpose: str = EMAIL_CODE_PURPOSE_REGISTER) -> None:
    """校验验证码；成功即失效，失败 5 次作废。"""
    email = email.strip().lower()
    fail_key = _code_fail_key(purpose, email)
    expected = cache.get(_code_key(purpose, email))
    if not expected:
        raise BusinessError("AUTH_CODE_INVALID", "验证码错误或已过期")

    if not secrets.compare_digest(str(expected), str(code).strip()):
        failures = cache.get(fail_key, 0) + 1
        if failures >= settings.AUTH_EMAIL_CODE_MAX_FAILURES:
            cache.delete(_code_key(purpose, email))
            cache.set(fail_key, failures, timeout=settings.AUTH_EMAIL_CODE_TTL_SECONDS)
        else:
            cache.set(fail_key, failures, timeout=settings.AUTH_EMAIL_CODE_TTL_SECONDS)
        raise BusinessError("AUTH_CODE_INVALID", "验证码错误或已过期")

    cache.delete(_code_key(purpose, email))
    cache.delete(fail_key)


# ---------------------------------------------------------------------------
# 注册
# ---------------------------------------------------------------------------


def _validate_password_strength(password: str) -> None:
    if not 8 <= len(password) <= 64:
        raise BusinessError("COMMON_VALIDATION_ERROR", "密码长度需为 8–64 位")
    if not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        raise BusinessError("COMMON_VALIDATION_ERROR", "密码需同时包含字母与数字")


def register_user(*, email: str, username: str, password: str, email_code: str):
    email = email.strip().lower()
    username = username.strip()

    _validate_password_strength(password)
    verify_email_code(email, email_code, EMAIL_CODE_PURPOSE_REGISTER)

    if User.objects.filter(email=email).exists():
        raise BusinessError("USER_EMAIL_EXISTS", "该邮箱已注册", http_status=409)
    if User.objects.filter(username__iexact=username).exists():
        raise BusinessError("USER_USERNAME_EXISTS", "该用户名已被占用", http_status=409)

    try:
        with transaction.atomic():
            user = User.objects.create(
                username=username,
                email=email,
                nickname=username,
                password=make_password(password),
            )
            customer_group, _ = Group.objects.get_or_create(name="customer")
            user.groups.add(customer_group)
    except IntegrityError as exc:  # 并发注册兜底
        raise BusinessError("USER_EMAIL_EXISTS", "该邮箱已注册", http_status=409) from exc

    return user


# ---------------------------------------------------------------------------
# 登录 / 令牌
# ---------------------------------------------------------------------------
def _login_fail_key(account: str) -> str:
    return f"auth:login_fail:{account.strip().lower()}"


def login_failure_count(account: str) -> int:
    return int(cache.get(_login_fail_key(account), 0))


def is_account_locked(account: str) -> bool:
    return login_failure_count(account) >= settings.AUTH_LOGIN_MAX_FAILURES


def authenticate_account(account: str, password: str):
    """用户名或邮箱 + 密码登录，失败计数达阈值后锁定 15 分钟。"""
    account = account.strip()
    if is_account_locked(account):
        raise BusinessError(
            "AUTH_ACCOUNT_LOCKED",
            "登录失败次数过多，账号已临时锁定，请 15 分钟后重试",
            http_status=423,
        )

    user = (
        User.objects.filter(is_deleted=False)
        .filter(Q(username__iexact=account) | Q(email=account.lower()))
        .first()
    )

    if user is None or not user.check_password(password):
        fails = login_failure_count(account) + 1
        cache.set(
            _login_fail_key(account),
            fails,
            timeout=settings.AUTH_LOGIN_LOCK_MINUTES * 60,
        )
        # 第 5 次失败仍返回凭证错误，下一次请求在入口处被锁定拦截（V1-5）
        raise BusinessError("AUTH_INVALID_CREDENTIALS", "账号或密码错误", http_status=401)

    if not user.is_active:
        raise BusinessError("AUTH_ACCOUNT_DISABLED", "账号已被禁用，请联系客服", http_status=403)

    cache.delete(_login_fail_key(account))
    user.mark_login()
    user.save(update_fields=["last_login_at", "updated_at"])
    return user


def issue_tokens(user) -> tuple[str, str]:
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)


def rotate_refresh_token(raw_refresh: str) -> tuple[str, str]:
    """刷新并轮换 refresh，旧令牌进入黑名单。"""
    from rest_framework_simplejwt.serializers import TokenRefreshSerializer

    serializer = TokenRefreshSerializer(data={"refresh": raw_refresh})
    try:
        serializer.is_valid(raise_exception=True)
    except TokenError as exc:
        raise BusinessError(
            "AUTH_REFRESH_REVOKED", "登录状态已失效，请重新登录", http_status=401
        ) from exc
    except Exception as exc:  # noqa: BLE001 - 统一收敛为 refresh 失效
        raise BusinessError(
            "AUTH_REFRESH_REVOKED", "登录状态已失效，请重新登录", http_status=401
        ) from exc
    return serializer.validated_data["access"], serializer.validated_data["refresh"]


def blacklist_refresh_token(raw_refresh: str) -> None:
    try:
        RefreshToken(raw_refresh).blacklist()
    except TokenError:
        # 已失效的 refresh 视作登出成功，保持幂等
        return


def revoke_all_refresh_tokens(user) -> None:
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


# ---------------------------------------------------------------------------
# 找回密码
# ---------------------------------------------------------------------------
def _reset_key(token: str) -> str:
    import hashlib

    return f"auth:pwd_reset:{hashlib.sha256(token.encode()).hexdigest()}"


def request_password_reset(email: str) -> None:
    """无论邮箱是否存在都返回成功，避免账号枚举。"""
    email = email.strip().lower()
    user = User.objects.filter(email=email, is_deleted=False, is_active=True).first()
    if user is None:
        return

    token = secrets.token_urlsafe(32)
    cache.set(_reset_key(token), user.pk, timeout=settings.AUTH_PASSWORD_RESET_TTL_SECONDS)
    link = f"{settings.APP_SITE_URL.rstrip('/')}/reset-password?token={token}"
    send_mail(
        subject="GUDA 商城密码重置",
        message=f"请在 30 分钟内访问以下链接重置密码（仅可使用一次）：\n{link}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )


def confirm_password_reset(token: str, new_password: str) -> None:
    _validate_password_strength(new_password)
    key = _reset_key(token)
    user_id = cache.get(key)
    if not user_id:
        raise BusinessError("AUTH_TOKEN_INVALID", "重置链接无效或已过期", http_status=400)

    user = User.objects.filter(pk=user_id, is_deleted=False).first()
    if user is None:
        cache.delete(key)
        raise BusinessError("AUTH_TOKEN_INVALID", "重置链接无效或已过期", http_status=400)

    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        revoke_all_refresh_tokens(user)
    cache.delete(key)


# ---------------------------------------------------------------------------
# 个人资料与头像
# ---------------------------------------------------------------------------
AVATAR_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
AVATAR_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
AVATAR_MAX_BYTES = 5 * 1024 * 1024
AVATAR_MAX_SIDE = 4096


def update_profile(user, data: dict):
    fields = [key for key in ("nickname", "gender", "birthday") if key in data]
    for key in fields:
        setattr(user, key, data[key])
    if fields:
        user.save(update_fields=[*fields, "updated_at"])
    return user


def save_avatar(user, uploaded_file) -> str:
    """校验图片并重命名存储，返回相对路径。"""
    filename = uploaded_file.name or ""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in AVATAR_ALLOWED_EXTENSIONS:
        raise BusinessError("COMMON_VALIDATION_ERROR", "仅支持 jpg/jpeg/png/webp 格式图片")
    if (uploaded_file.content_type or "") not in AVATAR_ALLOWED_CONTENT_TYPES:
        raise BusinessError("COMMON_VALIDATION_ERROR", "图片 MIME 类型不合法")
    if uploaded_file.size > AVATAR_MAX_BYTES:
        raise BusinessError("COMMON_VALIDATION_ERROR", "头像文件不能超过 5MB")

    try:
        image = Image.open(uploaded_file)
        image.verify()
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        width, height = image.size
        uploaded_file.seek(0)
    except (UnidentifiedImageError, OSError) as exc:
        raise BusinessError("COMMON_VALIDATION_ERROR", "图片文件已损坏或格式不正确") from exc

    if width > AVATAR_MAX_SIDE or height > AVATAR_MAX_SIDE:
        raise BusinessError("COMMON_VALIDATION_ERROR", "图片尺寸不能超过 4096px")

    content = uploaded_file.read()
    suffix = "jpg" if extension == "jpeg" else extension
    relative_path = f"avatars/{user.public_id}-{secrets.token_hex(4)}.{suffix}"
    old_path = user.avatar

    saved_path = default_storage.save(relative_path, ContentFile(content))
    user.avatar = saved_path
    user.save(update_fields=["avatar", "updated_at"])

    if old_path and old_path != saved_path:
        default_storage.delete(old_path)
    return saved_path


# ---------------------------------------------------------------------------
# 地址管理
# ---------------------------------------------------------------------------
ADDRESS_LIMIT = 20


def list_addresses(user):
    return Address.objects.filter(user=user).order_by("-is_default", "-created_at")


def create_address(user, data: dict) -> Address:
    payload = dict(data)
    phone = payload.pop("phone", "")
    with transaction.atomic():
        # 锁定用户行，串行化默认地址切换与数量上限校验
        User.objects.select_for_update().get(pk=user.pk)
        if Address.objects.filter(user=user).count() >= ADDRESS_LIMIT:
            raise BusinessError("USER_ADDRESS_LIMIT", "地址数量已达上限 20 条", http_status=422)

        is_default = bool(payload.pop("is_default", False))
        if not Address.objects.filter(user=user).exists():
            is_default = True
        if is_default:
            Address.objects.filter(user=user, is_default=True).update(is_default=False)

        address = Address(user=user, is_default=is_default, **payload)
        address.set_phone(phone)
        address.save()
    return address


def update_address(user, public_id: str, data: dict) -> Address:
    payload = dict(data)
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        address = Address.objects.filter(user=user, public_id=public_id).first()
        if address is None:
            raise BusinessError("COMMON_NOT_FOUND", "地址不存在", http_status=404)

        is_default = payload.pop("is_default", None)
        for key, value in payload.items():
            if key == "phone":
                address.set_phone(value)
            else:
                setattr(address, key, value)

        if is_default is not None:
            if is_default:
                Address.objects.filter(user=user, is_default=True).exclude(pk=address.pk).update(
                    is_default=False
                )
                address.is_default = True
            elif address.is_default:
                # 不允许把唯一默认地址取消，避免出现无默认地址
                pass
        address.save()
    return address


def set_default_address(user, public_id: str) -> Address:
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        address = Address.objects.filter(user=user, public_id=public_id).first()
        if address is None:
            raise BusinessError("COMMON_NOT_FOUND", "地址不存在", http_status=404)
        Address.objects.filter(user=user, is_default=True).exclude(pk=address.pk).update(
            is_default=False
        )
        address.is_default = True
        address.save(update_fields=["is_default", "updated_at"])
    return address


def delete_address(user, public_id: str) -> None:
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        address = Address.objects.filter(user=user, public_id=public_id).first()
        if address is None:
            raise BusinessError("COMMON_NOT_FOUND", "地址不存在", http_status=404)
        was_default = address.is_default
        address.delete()
        if was_default:
            fallback = Address.objects.filter(user=user).order_by("-created_at").first()
            if fallback is not None:
                fallback.is_default = True
                fallback.save(update_fields=["is_default", "updated_at"])
