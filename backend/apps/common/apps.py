from django.apps import AppConfig


class CommonConfig(AppConfig):
    name = "apps.common"
    label = "common"
    verbose_name = "公共基础"
    default_auto_field = "django.db.models.BigAutoField"
