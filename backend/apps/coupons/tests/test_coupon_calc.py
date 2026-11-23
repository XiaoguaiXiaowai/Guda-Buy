"""券试算规则：类型、门槛、范围、运费与边界。"""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.common.exceptions import BusinessError
from apps.coupons import services
from apps.coupons.models import Coupon, UserCoupon
from apps.coupons.tests.conftest import add_scope, make_coupon, make_user_coupon
from apps.orders.tests.conftest import build_order, make_sku


def _lines(*pairs):
    return [services.make_line(sku.product, sku.sale_price, quantity) for sku, quantity in pairs]


def test_fixed_coupon_discount_and_free_shipping(sku):
    coupon = make_coupon()
    result = services.evaluate_coupon(coupon, lines=_lines((sku, 1)), items_amount="120.00")
    assert result["usable"] is True
    assert result["discount_amount"] == Decimal("20.00")
    assert result["shipping_amount"] == Decimal("0.00")
    assert result["payable_amount"] == Decimal("100.00")


def test_fixed_coupon_below_min_amount(sku):
    coupon = make_coupon(min_amount="200.00")
    result = services.evaluate_coupon(coupon, lines=_lines((sku, 1)), items_amount="120.00")
    assert result["usable"] is False
    assert result["reason_code"] == "COUPON_MIN_AMOUNT_NOT_REACHED"
    assert result["reason_text"] == "未满 200.00 元"
    assert result["discount_amount"] == Decimal("0.00")


def test_discount_coupon(sku):
    coupon = make_coupon(coupon_type=Coupon.Type.DISCOUNT, value="0.90", min_amount="0")
    result = services.evaluate_coupon(coupon, lines=_lines((sku, 1)), items_amount="120.00")
    assert result["usable"] is True
    assert result["discount_amount"] == Decimal("12.00")
    assert result["payable_amount"] == Decimal("108.00")


def test_discount_coupon_rounds_half_up(db):
    from apps.catalog.models import Category, Product

    category = Category.objects.create(name="精度分类")
    product = Product.objects.create(
        category=category,
        name="精度商品",
        status=Product.Status.ON_SALE,
        price_min=Decimal("33.33"),
        price_max=Decimal("33.33"),
    )
    sku = make_sku(product, sku_code="ROUND-001", sale_price="33.33", stock=10)
    coupon = make_coupon(coupon_type=Coupon.Type.DISCOUNT, value="0.85", min_amount="0")
    result = services.evaluate_coupon(coupon, lines=_lines((sku, 3)), items_amount="99.99")
    assert result["discount_amount"] == Decimal("15.00")
    assert result["shipping_amount"] == Decimal("10.00")
    assert result["payable_amount"] == Decimal("94.99")


def test_free_shipping_coupon(other_sku):
    coupon = make_coupon(coupon_type=Coupon.Type.FREE_SHIPPING, value="0", min_amount="0")
    result = services.evaluate_coupon(coupon, lines=_lines((other_sku, 1)), items_amount="50.00")
    assert result["usable"] is True
    assert result["discount_amount"] == Decimal("0.00")
    assert result["shipping_amount"] == Decimal("0.00")
    assert result["payable_amount"] == Decimal("50.00")


def test_shipping_threshold_uses_post_discount_amount(other_sku):
    sku = make_sku(other_sku.product, sku_code="THRESHOLD-001", sale_price="105.00", stock=10)
    coupon = make_coupon(min_amount="100.00", value="20.00")
    result = services.evaluate_coupon(coupon, lines=_lines((sku, 1)), items_amount="105.00")
    assert result["discount_amount"] == Decimal("20.00")
    assert result["shipping_amount"] == Decimal("10.00")
    assert result["payable_amount"] == Decimal("95.00")


def test_product_scope_only_counts_matching_items(sku, other_sku):
    coupon = make_coupon(min_amount="0", value="30.00", scope_type=Coupon.ScopeType.PRODUCT)
    add_scope(coupon, product=sku.product)
    result = services.evaluate_coupon(
        coupon, lines=_lines((sku, 1), (other_sku, 1)), items_amount="170.00"
    )
    assert result["eligible_amount"] == Decimal("120.00")
    assert result["discount_amount"] == Decimal("30.00")
    assert result["payable_amount"] == Decimal("140.00")


def test_category_scope_limits_eligible_amount(category, other_sku):
    coupon = make_coupon(min_amount="0", value="30.00", scope_type=Coupon.ScopeType.CATEGORY)
    add_scope(coupon, category=category)
    result = services.evaluate_coupon(coupon, lines=_lines((other_sku, 1)), items_amount="50.00")
    assert result["usable"] is False
    assert result["reason_code"] == "COUPON_NOT_APPLICABLE"


def test_discount_clamped_to_one_cent(other_sku):
    coupon = make_coupon(min_amount="0", value="500.00")
    result = services.evaluate_coupon(coupon, lines=_lines((other_sku, 1)), items_amount="50.00")
    assert result["discount_amount"] == Decimal("49.99")
    assert result["payable_amount"] == Decimal("10.01")


def test_user_coupon_status_reasons(user, sku, address):
    coupon = make_coupon()
    order = build_order(user, address, sku)
    used = make_user_coupon(
        user, coupon, status=UserCoupon.Status.USED, order=order, used_at=timezone.now()
    )
    locked = make_user_coupon(user, coupon, status=UserCoupon.Status.LOCKED)
    expired = make_user_coupon(user, coupon, status=UserCoupon.Status.EXPIRED)

    assert (
        services.evaluate_user_coupon(used, lines=_lines((sku, 1)), items_amount="120.00")[
            "reason_text"
        ]
        == "优惠券已使用"
    )
    assert (
        services.evaluate_user_coupon(locked, lines=_lines((sku, 1)), items_amount="120.00")[
            "reason_code"
        ]
        == "COUPON_STATUS_CONFLICT"
    )
    assert (
        services.evaluate_user_coupon(expired, lines=_lines((sku, 1)), items_amount="120.00")[
            "reason_code"
        ]
        == "COUPON_EXPIRED"
    )


def test_user_coupon_expired_by_time(user, sku):
    coupon = make_coupon()
    user_coupon = make_user_coupon(user, coupon, expires_at=timezone.now())
    result = services.evaluate_user_coupon(
        user_coupon, lines=_lines((sku, 1)), items_amount="120.00"
    )
    assert result["usable"] is False
    assert result["reason_text"] == "优惠券已过期"


def test_evaluate_coupons_for_user_selects_coupon(user, sku):
    usable = make_user_coupon(user, make_coupon(name="可用券"))
    make_user_coupon(user, make_coupon(name="门槛券", min_amount="1000.00"))
    result = services.evaluate_coupons_for_user(
        user,
        lines=_lines((sku, 1)),
        items_amount="120.00",
        selected_public_id=usable.public_id,
    )
    assert len(result["evaluations"]) == 2
    assert result["selected"]["user_coupon"].public_id == usable.public_id
    assert result["selected"]["discount_amount"] == Decimal("20.00")


def test_evaluate_coupons_for_user_rejects_foreign_coupon(user, other_user, sku):
    foreign = make_user_coupon(other_user, make_coupon())
    with pytest.raises(BusinessError) as exc:
        services.evaluate_coupons_for_user(
            user,
            lines=_lines((sku, 1)),
            items_amount="120.00",
            selected_public_id=foreign.public_id,
        )
    assert exc.value.code == "COUPON_NOT_FOUND"


def test_lock_for_preview_raises_for_unusable(user, sku):
    user_coupon = make_user_coupon(user, make_coupon(min_amount="1000.00"))
    with pytest.raises(BusinessError) as exc:
        services.lock_for_preview(
            user, user_coupon.public_id, lines=_lines((sku, 1)), items_amount="120.00"
        )
    assert exc.value.code == "COUPON_MIN_AMOUNT_NOT_REACHED"
    assert exc.value.http_status == 422
