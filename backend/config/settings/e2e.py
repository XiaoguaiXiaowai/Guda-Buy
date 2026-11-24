"""E2E 测试环境：沿用 dev，验证码邮件落盘，并放宽限流以支撑自动化链路。"""

from .dev import *  # noqa: F403

EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = BASE_DIR / "logs" / "e2e-mail"  # noqa: F405

REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {
        **REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],  # noqa: F405
        "anon": "6000/min",
        "user": "6000/min",
        "login": "600/min",
        "register": "600/min",
        "email_code": "600/min",
    },
}
