"""敏感字段加解密（架构文档 6.5：手机号 AES-256-GCM + 检索哈希）。"""

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings


def _aes_key() -> bytes:
    """从环境变量派生固定长度密钥，兼容任意长度的配置值。"""
    raw = settings.FIELD_ENCRYPTION_KEY or settings.SECRET_KEY
    return hashlib.sha256(raw.encode("utf-8")).digest()


def encrypt_phone(phone: str) -> str:
    if not phone:
        return ""
    aesgcm = AESGCM(_aes_key())
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, phone.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_phone(token: str) -> str:
    if not token:
        return ""
    payload = base64.urlsafe_b64decode(token.encode("ascii"))
    nonce, ciphertext = payload[:12], payload[12:]
    return AESGCM(_aes_key()).decrypt(nonce, ciphertext, None).decode("utf-8")


def hash_phone(phone: str) -> str:
    """用于唯一性与检索，不可逆。"""
    return hashlib.sha256(phone.strip().encode("utf-8")).hexdigest()


def mask_phone(phone: str) -> str:
    """展示脱敏：138****1111。"""
    if not phone or len(phone) < 7:
        return phone
    return f"{phone[:3]}****{phone[-4:]}"
