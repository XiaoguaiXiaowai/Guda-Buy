"""账号接口限流：登录按账号、注册与验证码按 IP。"""

from rest_framework.throttling import SimpleRateThrottle

from apps.accounts.services import is_account_locked
from apps.common.exceptions import BusinessError


class LoginAccountThrottle(SimpleRateThrottle):
    scope = "login"

    def get_cache_key(self, request, view):  # noqa: ARG002
        account = ""
        if hasattr(request, "data") and isinstance(request.data, dict):
            account = str(request.data.get("account", "")).strip().lower()
        ident = account or self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}

    def allow_request(self, request, view):
        # 锁定期内即使密码正确也直接返回 423（迭代计划 V1-5）
        account = ""
        if hasattr(request, "data") and isinstance(request.data, dict):
            account = str(request.data.get("account", "")).strip()
        if account and is_account_locked(account):
            raise BusinessError(
                "AUTH_ACCOUNT_LOCKED",
                "登录失败次数过多，账号已临时锁定，请 15 分钟后重试",
                http_status=423,
            )
        return super().allow_request(request, view)


class RegisterIPThrottle(SimpleRateThrottle):
    scope = "register"

    def get_cache_key(self, request, view):  # noqa: ARG002
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class EmailCodeIPThrottle(SimpleRateThrottle):
    scope = "email_code"

    def get_cache_key(self, request, view):  # noqa: ARG002
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
