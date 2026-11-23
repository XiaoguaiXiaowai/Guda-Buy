"""优惠券领域服务：券模板管理、领券、试算、锁券/核销/退券与过期处理的唯一写入口。

金额口径统一走 `apps.orders.pricing`：商品小计 → 券抵扣 → 运费 → 应付。
"""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.core.cache import caches
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.catalog.models import Category, Product
from apps.common.exceptions import BusinessError
from apps.coupons.models import Coupon, CouponScope, UserCoupon
from apps.orders.pricing import calculate, money

CLAIM_LOCK_TTL_SECONDS = 10
CENT = Decimal("0.01")

REASON_HTTP_STATUS = {
    "COUPON_STATUS_CONFLICT": 409,
    "COUPON_EXPIRED": 422,
    "COUPON_NOT_APPLICABLE": 422,
    "COUPON_MIN_AMOUNT_NOT_REACHED": 422,
    "COUPON_NOT_FOUND": 404,
}


def _cache():
    return caches["default"]


def _claim_lock_key(coupon_id: int, user_id: int) -> str:
    return f"coupons:lock:claim:{coupon_id}:{user_id}"


# ---------------------------------------------------------------------------
# 适用范围与金额试算
# ---------------------------------------------------------------------------
def make_line(product, unit_price, quantity: int) -> dict:
    """构造适用性判断所需的行数据：商品、分类（含一级父类）与成交价。"""
    category = product.category
    category_ids = {category.id}
    if category.parent_id:
        category_ids.add(category.parent_id)
    return {
        "product_id": product.id,
        "category_ids": category_ids,
        "unit_price": money(unit_price),
        "quantity": quantity,
    }


def _scope_targets(coupon: Coupon) -> tuple[set[int], set[int]]:
    category_ids: set[int] = set()
    product_ids: set[int] = set()
    for scope in coupon.scopes.all():
        if scope.category_id:
            category_ids.add(scope.category_id)
        elif scope.product_id:
            product_ids.add(scope.product_id)
    return category_ids, product_ids


def eligible_amount(coupon: Coupon, lines: list[dict]) -> Decimal:
    """仅统计适用商品的小计；ALL 直接取全部商品金额。"""
    if coupon.scope_type == Coupon.ScopeType.ALL:
        return money(sum((line["unit_price"] * line["quantity"] for line in lines), Decimal("0")))

    category_ids, product_ids = _scope_targets(coupon)
    total = Decimal("0.00")
    for line in lines:
        if coupon.scope_type == Coupon.ScopeType.CATEGORY:
            matched = bool(line["category_ids"] & category_ids)
        else:
            matched = line["product_id"] in product_ids
        if matched:
            total += line["unit_price"] * line["quantity"]
    return money(total)


def _discount_for(coupon: Coupon, eligible: Decimal) -> Decimal:
    if coupon.coupon_type == Coupon.Type.FIXED:
        return money(min(coupon.value, eligible))
    if coupon.coupon_type == Coupon.Type.DISCOUNT:
        raw = eligible * (Decimal("1") - coupon.value)
        return raw.quantize(CENT, rounding=ROUND_HALF_UP)
    return Decimal("0.00")


def _unusable(reason_code: str, reason_text: str, *, items_amount, eligible) -> dict:
    default = calculate(items_amount)
    return {
        "usable": False,
        "reason_code": reason_code,
        "reason_text": reason_text,
        "http_status": REASON_HTTP_STATUS.get(reason_code, 422),
        "free_shipping": False,
        "eligible_amount": money(eligible),
        "discount_amount": default["discount_amount"],
        "shipping_amount": default["shipping_amount"],
        "payable_amount": default["payable_amount"],
    }


def evaluate_coupon(coupon: Coupon, *, lines: list[dict], items_amount, now=None) -> dict:
    """按券模板计算可用性与抵扣金额；不校验用户领取状态。"""
    now = now or timezone.now()
    items_amount = money(items_amount)
    eligible = eligible_amount(coupon, lines)

    if coupon.status != Coupon.Status.ACTIVE:
        return _unusable(
            "COUPON_STATUS_CONFLICT", "活动已停止", items_amount=items_amount, eligible=eligible
        )
    if now < coupon.valid_from:
        return _unusable(
            "COUPON_EXPIRED", "活动未开始", items_amount=items_amount, eligible=eligible
        )
    if now > coupon.valid_to:
        return _unusable(
            "COUPON_EXPIRED", "优惠券已过期", items_amount=items_amount, eligible=eligible
        )
    if eligible <= 0:
        return _unusable(
            "COUPON_NOT_APPLICABLE",
            "不适用于当前商品",
            items_amount=items_amount,
            eligible=eligible,
        )
    if eligible < coupon.min_amount:
        return _unusable(
            "COUPON_MIN_AMOUNT_NOT_REACHED",
            f"未满 {money(coupon.min_amount):.2f} 元",
            items_amount=items_amount,
            eligible=eligible,
        )

    amounts = calculate(
        items_amount,
        discount_amount=_discount_for(coupon, eligible),
        free_shipping=coupon.is_free_shipping,
    )
    return {
        "usable": True,
        "reason_code": "",
        "reason_text": "",
        "http_status": 200,
        "free_shipping": coupon.is_free_shipping,
        "eligible_amount": eligible,
        **{key: amounts[key] for key in ("discount_amount", "shipping_amount", "payable_amount")},
    }


def evaluate_user_coupon(user_coupon: UserCoupon, *, lines, items_amount, now=None) -> dict:
    """在模板校验前先检查领取记录状态，返回可直接展示的试算结果。"""
    now = now or timezone.now()
    coupon = user_coupon.coupon
    if user_coupon.status == UserCoupon.Status.USED:
        return _unusable(
            "COUPON_STATUS_CONFLICT", "优惠券已使用", items_amount=items_amount, eligible=0
        )
    if user_coupon.status == UserCoupon.Status.LOCKED:
        return _unusable(
            "COUPON_STATUS_CONFLICT", "优惠券已锁定", items_amount=items_amount, eligible=0
        )
    if user_coupon.status == UserCoupon.Status.EXPIRED or user_coupon.expires_at <= now:
        return _unusable("COUPON_EXPIRED", "优惠券已过期", items_amount=items_amount, eligible=0)
    return evaluate_coupon(coupon, lines=lines, items_amount=items_amount, now=now)


def evaluate_coupons_for_user(
    user, *, lines, items_amount, selected_public_id: str = "", statuses=None
) -> dict:
    """结算试算：返回用户全部未使用券的可用性与金额，附带被选中的券。"""
    statuses = statuses or [UserCoupon.Status.UNUSED]
    items_amount = money(items_amount)
    now = timezone.now()
    queryset = (
        UserCoupon.objects.filter(user=user, status__in=statuses)
        .select_related("coupon")
        .prefetch_related("coupon__scopes")
        .order_by("-claimed_at", "-id")
    )
    evaluations = []
    selected = None
    for user_coupon in queryset:
        result = evaluate_user_coupon(user_coupon, lines=lines, items_amount=items_amount, now=now)
        result["user_coupon"] = user_coupon
        result["coupon"] = user_coupon.coupon
        evaluations.append(result)
        if selected_public_id and user_coupon.public_id == selected_public_id:
            selected = result
    if selected_public_id and selected is None:
        raise BusinessError("COUPON_NOT_FOUND", "优惠券不存在", http_status=404)
    return {"evaluations": evaluations, "selected": selected, "items_amount": items_amount}


# ---------------------------------------------------------------------------
# 领券
# ---------------------------------------------------------------------------
def _ensure_claimable(coupon: Coupon, now) -> None:
    if coupon.status != Coupon.Status.ACTIVE:
        raise BusinessError("COUPON_STATUS_CONFLICT", "活动未开始或已停止", http_status=409)
    if now < coupon.valid_from:
        raise BusinessError("COUPON_EXPIRED", "活动未开始", http_status=422)
    if now > coupon.valid_to:
        raise BusinessError("COUPON_EXPIRED", "优惠券已过期", http_status=422)
    if coupon.claimed_quantity >= coupon.total_quantity:
        raise BusinessError("COUPON_SOLD_OUT", "优惠券已领完", http_status=422)


@transaction.atomic
def _claim_atomic(user, coupon_id: int) -> UserCoupon:
    coupon = Coupon.objects.select_for_update().filter(pk=coupon_id, is_deleted=False).first()
    if coupon is None:
        raise BusinessError("COUPON_NOT_FOUND", "优惠券不存在", http_status=404)
    now = timezone.now()
    _ensure_claimable(coupon, now)

    claimed = UserCoupon.objects.filter(user=user, coupon=coupon).count()
    if claimed >= coupon.per_user_limit:
        raise BusinessError(
            "COUPON_LIMIT_REACHED",
            "已达领取上限",
            http_status=422,
            detail={"per_user_limit": coupon.per_user_limit},
        )

    updated = Coupon.objects.filter(pk=coupon.pk, claimed_quantity__lt=F("total_quantity")).update(
        claimed_quantity=F("claimed_quantity") + 1, updated_at=now
    )
    if not updated:
        raise BusinessError("COUPON_SOLD_OUT", "优惠券已领完", http_status=422)

    return UserCoupon.objects.create(
        user=user,
        coupon=coupon,
        status=UserCoupon.Status.UNUSED,
        claimed_at=now,
        expires_at=coupon.valid_to,
    )


def claim_coupon(user, public_id: str) -> UserCoupon:
    """领券入口：Redis 短锁防同用户重复点击，总量由数据库条件递增兜底。"""
    coupon = Coupon.objects.filter(public_id=public_id, is_deleted=False).first()
    if coupon is None:
        raise BusinessError("COUPON_NOT_FOUND", "优惠券不存在", http_status=404)

    lock_key = _claim_lock_key(coupon.id, user.id)
    if not _cache().add(lock_key, "1", timeout=CLAIM_LOCK_TTL_SECONDS):
        raise BusinessError("COUPON_STATUS_CONFLICT", "领取过于频繁，请稍后重试", http_status=409)
    try:
        return _claim_atomic(user, coupon.id)
    finally:
        _cache().delete(lock_key)


# ---------------------------------------------------------------------------
# 下单锁券、支付核销、取消退券
# ---------------------------------------------------------------------------
def lock_for_order(user, public_id: str, *, lines, items_amount, order) -> dict:
    """下单事务内锁券：校验通过后置 LOCKED 并绑定订单，返回抵扣金额。"""
    user_coupon = (
        UserCoupon.objects.select_for_update()
        .select_related("coupon")
        .filter(public_id=public_id, user=user)
        .first()
    )
    if user_coupon is None:
        raise BusinessError("COUPON_NOT_FOUND", "优惠券不存在", http_status=404)

    result = evaluate_user_coupon(user_coupon, lines=lines, items_amount=items_amount)
    if not result["usable"]:
        raise BusinessError(
            result["reason_code"],
            result["reason_text"],
            http_status=result["http_status"],
        )

    user_coupon.status = UserCoupon.Status.LOCKED
    user_coupon.order = order
    user_coupon.used_at = None
    user_coupon.save(update_fields=["status", "order", "used_at", "updated_at"])
    return result


def lock_for_preview(user, public_id: str, *, lines, items_amount) -> dict:
    """结算预览用：只读校验，不落库。"""
    user_coupon = (
        UserCoupon.objects.select_related("coupon")
        .prefetch_related("coupon__scopes")
        .filter(public_id=public_id, user=user)
        .first()
    )
    if user_coupon is None:
        raise BusinessError("COUPON_NOT_FOUND", "优惠券不存在", http_status=404)
    result = evaluate_user_coupon(user_coupon, lines=lines, items_amount=items_amount)
    if not result["usable"]:
        raise BusinessError(
            result["reason_code"],
            result["reason_text"],
            http_status=result["http_status"],
        )
    result["user_coupon"] = user_coupon
    result["coupon"] = user_coupon.coupon
    return result


def mark_used_for_order(order) -> None:
    """支付成功：锁定券置 USED；重复回调时状态已不是 LOCKED，天然幂等。"""
    user_coupon = UserCoupon.objects.select_for_update().filter(order=order).first()
    if user_coupon is None or user_coupon.status != UserCoupon.Status.LOCKED:
        return
    user_coupon.status = UserCoupon.Status.USED
    user_coupon.used_at = timezone.now()
    user_coupon.save(update_fields=["status", "used_at", "updated_at"])


def release_for_order(order) -> None:
    """取消/超时退券：解除订单绑定；已过期则置 EXPIRED，否则回到 UNUSED。"""
    user_coupon = UserCoupon.objects.select_for_update().filter(order=order).first()
    if user_coupon is None or user_coupon.status != UserCoupon.Status.LOCKED:
        return
    now = timezone.now()
    user_coupon.status = (
        UserCoupon.Status.EXPIRED if user_coupon.expires_at <= now else UserCoupon.Status.UNUSED
    )
    user_coupon.order = None
    user_coupon.used_at = None
    user_coupon.save(update_fields=["status", "order", "used_at", "updated_at"])


# ---------------------------------------------------------------------------
# 过期处理与到期提醒
# ---------------------------------------------------------------------------
def expire_user_coupons(limit: int | None = None) -> int:
    """每日任务：未使用且已过期的券批量置 EXPIRED，可重复执行。"""
    now = timezone.now()
    queryset = UserCoupon.objects.filter(
        status=UserCoupon.Status.UNUSED, expires_at__lt=now
    ).values_list("id", flat=True)
    if limit:
        queryset = queryset[:limit]
    return UserCoupon.objects.filter(id__in=list(queryset)).update(
        status=UserCoupon.Status.EXPIRED, updated_at=now
    )


def expiring_user_coupons(days: int) -> list[UserCoupon]:
    """到期前 N 天的未使用券；I8 通知模块据此生成 COUPON_EXPIRING 消息。"""
    now = timezone.now()
    return list(
        UserCoupon.objects.filter(
            status=UserCoupon.Status.UNUSED,
            expires_at__gte=now,
            expires_at__lte=now + timedelta(days=days),
        ).select_related("coupon", "user")
    )


# ---------------------------------------------------------------------------
# 后台券管理
# ---------------------------------------------------------------------------
COUPON_WRITABLE_FIELDS = (
    "name",
    "coupon_type",
    "value",
    "min_amount",
    "total_quantity",
    "per_user_limit",
    "scope_type",
    "valid_from",
    "valid_to",
    "status",
)


def _resolve_scope_targets(
    scope_type: str, category_public_ids: list[str], product_public_ids: list[str]
) -> tuple[list[Category], list[Product]]:
    categories: list[Category] = []
    products: list[Product] = []
    if scope_type == Coupon.ScopeType.ALL:
        if category_public_ids or product_public_ids:
            raise BusinessError(
                "COMMON_VALIDATION_ERROR", "全场券无需配置适用范围", http_status=400
            )
        return categories, products

    if scope_type == Coupon.ScopeType.CATEGORY:
        if not category_public_ids or product_public_ids:
            raise BusinessError(
                "COMMON_VALIDATION_ERROR", "分类券需且仅需配置分类", http_status=400
            )
        categories = list(Category.objects.filter(public_id__in=category_public_ids).order_by("id"))
        if len(categories) != len(set(category_public_ids)):
            raise BusinessError("COMMON_VALIDATION_ERROR", "存在无效的分类", http_status=400)
        return categories, products

    if not product_public_ids or category_public_ids:
        raise BusinessError("COMMON_VALIDATION_ERROR", "商品券需且仅需配置商品", http_status=400)
    products = list(
        Product.objects.filter(public_id__in=product_public_ids, is_deleted=False).order_by("id")
    )
    if len(products) != len(set(product_public_ids)):
        raise BusinessError("COMMON_VALIDATION_ERROR", "存在无效的商品", http_status=400)
    return categories, products


def _replace_scopes(coupon: Coupon, categories: list[Category], products: list[Product]) -> None:
    coupon.scopes.all().delete()
    CouponScope.objects.bulk_create(
        [CouponScope(coupon=coupon, category=category) for category in categories]
        + [CouponScope(coupon=coupon, product=product) for product in products]
    )


def create_coupon(operator, data: dict) -> Coupon:
    """运营创建券：校验适用范围后写入模板与范围明细。"""
    categories, products = _resolve_scope_targets(
        data["scope_type"],
        data.get("scope_category_public_ids") or [],
        data.get("scope_product_public_ids") or [],
    )
    with transaction.atomic():
        coupon = Coupon.objects.create(
            **{field: data[field] for field in COUPON_WRITABLE_FIELDS if field in data},
            created_by=operator,
            updated_by=operator,
        )
        _replace_scopes(coupon, categories, products)
    return coupon


def update_coupon(operator, public_id: str, data: dict) -> Coupon:
    """仅未开始发放（claimed_quantity=0）的券可修改。"""
    coupon = Coupon.objects.filter(public_id=public_id, is_deleted=False).first()
    if coupon is None:
        raise BusinessError("COUPON_NOT_FOUND", "优惠券不存在", http_status=404)
    if coupon.claimed_quantity > 0:
        raise BusinessError("COUPON_STATUS_CONFLICT", "券已开始发放，不能修改", http_status=409)

    scope_type = data.get("scope_type", coupon.scope_type)
    category_ids = data.get("scope_category_public_ids")
    product_ids = data.get("scope_product_public_ids")
    scopes_provided = category_ids is not None or product_ids is not None
    if "scope_type" in data and scope_type != Coupon.ScopeType.ALL and not scopes_provided:
        raise BusinessError(
            "COMMON_VALIDATION_ERROR", "切换适用范围时需同时提交范围明细", http_status=400
        )
    if scopes_provided:
        categories, products = _resolve_scope_targets(
            scope_type, category_ids or [], product_ids or []
        )
    else:
        categories, products = [], []

    with transaction.atomic():
        for field in (
            "name",
            "coupon_type",
            "value",
            "min_amount",
            "total_quantity",
            "per_user_limit",
            "scope_type",
            "valid_from",
            "valid_to",
            "status",
        ):
            if field in data:
                setattr(coupon, field, data[field])
        coupon.updated_by = operator
        coupon.save()
        if scopes_provided or "scope_type" in data:
            _replace_scopes(coupon, categories, products)
    return coupon
