"""优惠券只读查询与出参组装。"""

from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone

from apps.coupons.models import Coupon, UserCoupon

COUPON_TYPE_TEXT = dict(Coupon.Type.choices)
SCOPE_TYPE_TEXT = dict(Coupon.ScopeType.choices)
COUPON_STATUS_TEXT = dict(Coupon.Status.choices)
USER_COUPON_STATUS_TEXT = dict(UserCoupon.Status.choices)


def _money(value) -> str:
    return f"{Decimal(value or 0):.2f}"


def _scope_summary(coupon: Coupon) -> str:
    if coupon.scope_type == Coupon.ScopeType.ALL:
        return "全场通用"
    scopes = list(coupon.scopes.all())
    if coupon.scope_type == Coupon.ScopeType.CATEGORY:
        names = [scope.category.name for scope in scopes if scope.category_id]
        return "分类：" + "、".join(names[:3]) + ("等" if len(names) > 3 else "")
    names = [scope.product.name for scope in scopes if scope.product_id]
    return "商品：" + "、".join(names[:3]) + ("等" if len(names) > 3 else "")


def coupon_brief(coupon: Coupon) -> dict:
    return {
        "public_id": coupon.public_id,
        "name": coupon.name,
        "coupon_type": coupon.coupon_type,
        "coupon_type_text": COUPON_TYPE_TEXT.get(coupon.coupon_type, coupon.coupon_type),
        "value": _money(coupon.value),
        "min_amount": _money(coupon.min_amount),
        "per_user_limit": coupon.per_user_limit,
        "scope_type": coupon.scope_type,
        "scope_text": SCOPE_TYPE_TEXT.get(coupon.scope_type, coupon.scope_type),
        "scope_summary": _scope_summary(coupon),
        "total_quantity": coupon.total_quantity,
        "claimed_quantity": coupon.claimed_quantity,
        "valid_from": coupon.valid_from,
        "valid_to": coupon.valid_to,
        "status": coupon.status,
        "status_text": COUPON_STATUS_TEXT.get(coupon.status, coupon.status),
    }


def evaluation_payload(evaluation: dict) -> dict:
    """券试算结果：可用性、不可用原因与抵扣/运费/应付金额。"""
    user_coupon: UserCoupon = evaluation["user_coupon"]
    coupon: Coupon = evaluation["coupon"]
    payload = coupon_brief(coupon)
    payload.update(
        {
            "user_coupon_id": user_coupon.public_id,
            "status": user_coupon.status,
            "status_text": USER_COUPON_STATUS_TEXT.get(user_coupon.status, user_coupon.status),
            "claimed_at": user_coupon.claimed_at,
            "expires_at": user_coupon.expires_at,
            "usable": evaluation["usable"],
            "reason": evaluation["reason_text"],
            "eligible_amount": _money(evaluation["eligible_amount"]),
            "discount_amount": _money(evaluation["discount_amount"]),
            "shipping_amount": _money(evaluation["shipping_amount"]),
            "payable_amount": _money(evaluation["payable_amount"]),
        }
    )
    return payload


def user_coupon_payload(user_coupon: UserCoupon) -> dict:
    coupon = user_coupon.coupon
    return {
        "public_id": user_coupon.public_id,
        "status": user_coupon.status,
        "status_text": USER_COUPON_STATUS_TEXT.get(user_coupon.status, user_coupon.status),
        "claimed_at": user_coupon.claimed_at,
        "used_at": user_coupon.used_at,
        "expires_at": user_coupon.expires_at,
        "order_no": user_coupon.order.order_no if user_coupon.order_id else "",
        "coupon": coupon_brief(coupon),
    }


def my_coupons(user) -> dict:
    """我的券按未使用/已使用/已过期分组；未使用但已过有效期的归入已过期。"""
    now = timezone.now()
    queryset = (
        UserCoupon.objects.filter(user=user)
        .select_related("coupon", "order")
        .prefetch_related("coupon__scopes")
        .order_by("-claimed_at", "-id")
    )
    groups: dict[str, list] = {"unused": [], "used": [], "expired": []}
    for user_coupon in queryset:
        payload = user_coupon_payload(user_coupon)
        if user_coupon.status == UserCoupon.Status.USED:
            groups["used"].append(payload)
        elif user_coupon.status == UserCoupon.Status.EXPIRED or user_coupon.expires_at <= now:
            groups["expired"].append(payload)
        else:
            groups["unused"].append(payload)
    return {
        **groups,
        "counts": {key: len(value) for key, value in groups.items()},
    }


def available_coupons(user) -> list[dict]:
    """可领取券列表：进行中且在有效期内，附带本人已领数量与可领状态。"""
    now = timezone.now()
    coupons = (
        Coupon.objects.filter(
            status=Coupon.Status.ACTIVE,
            is_deleted=False,
            valid_from__lte=now,
            valid_to__gte=now,
        )
        .prefetch_related("scopes__category", "scopes__product")
        .order_by("min_amount", "id")
    )
    claimed_counts = dict(
        UserCoupon.objects.filter(user=user, coupon__in=coupons)
        .values("coupon_id")
        .annotate(total=Count("id"))
        .values_list("coupon_id", "total")
    )
    payloads = []
    for coupon in coupons:
        claimed_by_me = claimed_counts.get(coupon.id, 0)
        sold_out = coupon.claimed_quantity >= coupon.total_quantity
        limit_reached = claimed_by_me >= coupon.per_user_limit
        payload = coupon_brief(coupon)
        payload.update(
            {
                "claimed_by_me": claimed_by_me,
                "can_claim": not sold_out and not limit_reached,
                "reason": "已领完" if sold_out else ("已达领取上限" if limit_reached else ""),
            }
        )
        payloads.append(payload)
    return payloads


def admin_coupon_queryset(params):
    queryset = (
        Coupon.objects.filter(is_deleted=False)
        .prefetch_related("scopes__category", "scopes__product")
        .annotate(
            used_quantity=Count(
                "user_coupons",
                filter=Q(user_coupons__status=UserCoupon.Status.USED),
                distinct=True,
            )
        )
    )
    status = (params.get("status") or "").strip().upper()
    if status in Coupon.Status.values:
        queryset = queryset.filter(status=status)
    coupon_type = (params.get("coupon_type") or "").strip().upper()
    if coupon_type in Coupon.Type.values:
        queryset = queryset.filter(coupon_type=coupon_type)
    keyword = (params.get("keyword") or "").strip()[:60]
    if keyword:
        queryset = queryset.filter(name__icontains=keyword)
    return queryset.order_by("-created_at", "-id")


def admin_coupon_payload(coupon: Coupon) -> dict:
    payload = coupon_brief(coupon)
    scopes = list(coupon.scopes.all())
    payload.update(
        {
            "used_quantity": getattr(coupon, "used_quantity", 0),
            "scope_categories": [
                {"public_id": scope.category.public_id, "name": scope.category.name}
                for scope in scopes
                if scope.category_id
            ],
            "scope_products": [
                {"public_id": scope.product.public_id, "name": scope.product.name}
                for scope in scopes
                if scope.product_id
            ],
            "created_at": coupon.created_at,
            "updated_at": coupon.updated_at,
        }
    )
    return payload


def order_coupon_payload(order) -> dict | None:
    """订单使用的券（含取消退券后的历史记录）。"""
    user_coupon = order.user_coupon
    if user_coupon is None:
        return None
    return {
        "public_id": user_coupon.public_id,
        "status": user_coupon.status,
        "status_text": USER_COUPON_STATUS_TEXT.get(user_coupon.status, user_coupon.status),
        "name": user_coupon.coupon.name,
        "coupon_type": user_coupon.coupon.coupon_type,
        "coupon_type_text": COUPON_TYPE_TEXT.get(
            user_coupon.coupon.coupon_type, user_coupon.coupon.coupon_type
        ),
        "value": _money(user_coupon.coupon.value),
    }


__all__ = [
    "available_coupons",
    "admin_coupon_payload",
    "admin_coupon_queryset",
    "coupon_brief",
    "evaluation_payload",
    "my_coupons",
    "order_coupon_payload",
    "user_coupon_payload",
]
