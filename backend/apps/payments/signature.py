"""模拟支付回调签名：HMAC-SHA256(payment_no + amount + secret)。

密钥只从环境变量 `PAYMENT_CALLBACK_SECRET` 读取，未配置时拒绝签名。
"""

import hashlib
import hmac
from decimal import Decimal

from django.conf import settings

from apps.common.exceptions import BusinessError


def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"))


def _secret() -> str:
    secret = (settings.PAYMENT_CALLBACK_SECRET or "").strip()
    if not secret:
        raise BusinessError("COMMON_INTERNAL_ERROR", "支付回调密钥未配置", http_status=500)
    return secret


def sign_payment(payment_no: str, amount) -> str:
    """按 `payment_no + amount(两位小数字符串)` 计算签名。"""
    message = f"{payment_no}{_money(amount):.2f}"
    return hmac.new(_secret().encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_payment_signature(payment_no: str, amount, signature: str) -> bool:
    expected = sign_payment(payment_no, amount)
    return hmac.compare_digest(expected, (signature or "").strip())
