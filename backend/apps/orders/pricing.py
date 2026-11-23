"""订单金额纯计算：金额精度、运费门槛与应付口径集中在此，供订单与优惠券模块复用。

计算顺序固定为：商品小计 → 优惠券抵扣 → 运费 → 应付金额；
运费按抵扣后的商品实付金额判断是否达到免邮门槛（架构文档 10.2 金额规则）。
"""

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

CENT = Decimal("0.01")
MIN_PAYABLE = Decimal("0.01")


def money(value) -> Decimal:
    """统一保留两位小数并四舍五入。"""
    return Decimal(value or 0).quantize(CENT, rounding=ROUND_HALF_UP)


def clamp_discount(discount, items_amount) -> Decimal:
    """抵扣不得超过商品小计，且抵扣后商品金额不低于 0.01 元。"""
    discount = money(discount)
    if items_amount <= 0:
        return Decimal("0.00")
    limit = max(money(items_amount) - MIN_PAYABLE, Decimal("0.00"))
    return min(discount, limit)


def shipping_amount(taxable_amount) -> Decimal:
    """商品实付满阈值免运费，否则收固定运费。"""
    threshold = Decimal(settings.ORDER_FREE_SHIPPING_THRESHOLD)
    if money(taxable_amount) >= threshold:
        return Decimal("0.00")
    return money(settings.ORDER_SHIPPING_AMOUNT)


def calculate(items_amount, *, discount_amount=Decimal("0.00"), free_shipping=False) -> dict:
    """按固定顺序计算优惠、运费与应付；`free_shipping` 表示免邮券命中。"""
    items_amount = money(items_amount)
    discount_amount = clamp_discount(discount_amount, items_amount)
    taxable_amount = money(items_amount - discount_amount)
    shipping = Decimal("0.00") if free_shipping else shipping_amount(taxable_amount)
    return {
        "items_amount": items_amount,
        "discount_amount": discount_amount,
        "taxable_amount": taxable_amount,
        "shipping_amount": money(shipping),
        "payable_amount": money(taxable_amount + shipping),
    }
