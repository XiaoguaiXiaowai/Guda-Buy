"""Django Admin：仅用于开发与运维应急，前台业务不依赖。"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import Address, User


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0
    fields = ("receiver_name", "province", "city", "district", "detail", "is_default")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "nickname", "is_active", "is_staff", "created_at")
    list_filter = ("is_active", "is_staff", "gender")
    search_fields = ("username", "email", "nickname", "public_id")
    ordering = ("-created_at",)
    inlines = [AddressInline]
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "会员资料",
            {
                "fields": (
                    "public_id",
                    "nickname",
                    "gender",
                    "birthday",
                    "avatar",
                    "last_login_at",
                    "is_deleted",
                    "deleted_at",
                )
            },
        ),
    )
    readonly_fields = ("public_id", "created_at", "updated_at", "last_login_at")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("receiver_name", "user", "province", "city", "district", "is_default")
    search_fields = ("receiver_name", "user__username", "user__email", "public_id")
    list_filter = ("is_default", "province")
