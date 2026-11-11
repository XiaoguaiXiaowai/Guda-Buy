import pytest
from django.contrib.auth.models import Group

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_init_roles_creates_four_groups_and_permissions():
    from django.core.management import call_command

    call_command("init_roles")

    names = set(Group.objects.values_list("name", flat=True))
    assert {"customer", "support", "operator", "admin"} <= names

    admin = Group.objects.get(name="admin")
    assert admin.permissions.filter(codename="change_user_role").exists()
    assert admin.permissions.count() >= 1

    customer = Group.objects.get(name="customer")
    assert customer.permissions.count() == 0


def test_user_public_id_and_email_normalization():
    user = User.objects.create_user(
        username="buyer01", email="BUYER@Example.COM", password="Passw0rd123"
    )
    assert len(user.public_id) == 32
    assert user.email == "buyer@example.com"
    assert user.nickname == "buyer01"


def test_phone_encryption_roundtrip(user):
    user.set_phone("13800138000")
    user.save(update_fields=["phone_encrypted", "phone_hash"])

    user.refresh_from_db()
    assert user.phone_encrypted != "13800138000"
    assert user.phone_hash != "13800138000"
    assert user.phone == "13800138000"
