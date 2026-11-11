"""账号只读查询。"""

from apps.accounts.models import Address


def get_user_address(user, public_id: str):
    return Address.objects.filter(user=user, public_id=public_id).first()
