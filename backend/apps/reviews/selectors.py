"""评价查询与出参组装：公开列表、聚合、订单可评状态与后台列表。"""

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Count
from django.utils import timezone

from apps.reviews.models import Review

STATUS_TEXT = dict(Review.Status.choices)


def _format_average(value) -> str:
    return f"{value:.1f}" if value is not None else "0.0"


def _masked_nickname(nickname: str) -> str:
    """匿名评价展示：保留首字，其余脱敏，绝不返回用户名。"""
    nickname = (nickname or "").strip()
    if not nickname:
        return "匿名用户"
    return f"{nickname[0]}**"


def review_summary(product_id: int) -> dict:
    """按商品聚合已通过评价：平均分、总数与星级分布。"""
    rows = (
        Review.objects.filter(
            product_id=product_id,
            status=Review.Status.APPROVED,
            is_deleted=False,
        )
        .values("rating")
        .annotate(count=Count("id"))
    )
    distribution = {str(star): 0 for star in range(5, 0, -1)}
    total = 0
    weighted = 0
    for row in rows:
        count = row["count"]
        distribution[str(row["rating"])] = count
        total += count
        weighted += row["rating"] * count
    average = round(weighted / total, 1) if total else 0
    return {
        "average": _format_average(average),
        "count": total,
        "distribution": distribution,
    }


def _image_payload(image) -> dict:
    return {
        "public_id": image.public_id,
        "image": image.image,
        "sort_order": image.sort_order,
    }


def public_review_payload(review: Review) -> dict:
    """前台展示：匿名时昵称脱敏、头像不返回，始终不含 username。"""
    anonymous = review.is_anonymous
    user = review.user
    nickname = _masked_nickname(user.nickname) if anonymous else (user.nickname or user.username)
    return {
        "public_id": review.public_id,
        "rating": review.rating,
        "content": review.content,
        "is_anonymous": anonymous,
        "display_name": nickname,
        "avatar": "" if anonymous else user.avatar,
        "sku_spec": review.sku.spec_text,
        "images": [_image_payload(image) for image in review.images.all()],
        "created_at": review.created_at,
    }


def review_image_payload(image) -> dict:
    return _image_payload(image)


def order_review_payload(review: Review | None) -> dict | None:
    """本人视角：包含审核状态、驳回原因与图片，用于评价表单回填。"""
    if review is None:
        return None
    return {
        "public_id": review.public_id,
        "order_no": review.order.order_no,
        "product_public_id": review.product.public_id,
        "product_name": review.product.name,
        "sku_public_id": review.sku.public_id,
        "sku_spec": review.sku.spec_text,
        "rating": review.rating,
        "content": review.content,
        "status": review.status,
        "status_text": STATUS_TEXT.get(review.status, review.status),
        "reject_reason": review.reject_reason,
        "is_anonymous": review.is_anonymous,
        "images": [_image_payload(image) for image in review.images.all()],
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }


def review_deadline(order):
    if order.completed_at is None:
        return None
    return order.completed_at + timedelta(days=settings.REVIEW_WINDOW_DAYS)


def eligibility_payload(order, review: Review | None) -> dict:
    """订单可评状态：仅已完成且未超过评价窗口；驳回后可覆盖重提。"""
    deadline = review_deadline(order)
    can_review = False
    reason = ""

    if order.status != order.Status.COMPLETED:
        reason = "订单未完成，暂不可评价"
    elif deadline is None or timezone.now() > deadline:
        reason = "已超过评价期限"
    elif review is not None and review.status == Review.Status.PENDING:
        reason = "评价待审核"
    elif review is not None and review.status == Review.Status.APPROVED:
        reason = "该订单已评价"
    else:
        can_review = True

    items = [
        {
            "sku_public_id": item.sku.public_id,
            "product_name": item.sku.product.name,
            "sku_spec": item.sku.spec_text,
        }
        for item in order.items.all()
    ]

    return {
        "order_no": order.order_no,
        "can_review": can_review,
        "reason": reason,
        "requires_sku": len(items) > 1,
        "items": items,
        "review": order_review_payload(review),
        "window_expires_at": deadline,
    }


def public_review_queryset(product_public_id: str):
    return (
        Review.objects.filter(
            product__public_id=product_public_id,
            product__is_deleted=False,
            status=Review.Status.APPROVED,
            is_deleted=False,
        )
        .select_related("user", "sku")
        .prefetch_related("images")
        .order_by("-created_at", "-id")
    )


def admin_review_queryset(params) -> models.QuerySet:
    queryset = (
        Review.objects.filter(is_deleted=False)
        .select_related("user", "product", "sku", "order")
        .prefetch_related("images")
    )

    status = (params.get("status") or "").strip().upper()
    if status in Review.Status.values:
        queryset = queryset.filter(status=status)

    rating = (params.get("rating") or "").strip()
    if rating.isdigit() and 1 <= int(rating) <= 5:
        queryset = queryset.filter(rating=int(rating))

    keyword = (params.get("keyword") or "").strip()
    if keyword:
        queryset = queryset.filter(
            models.Q(order__order_no__icontains=keyword)
            | models.Q(product__name__icontains=keyword)
            | models.Q(content__icontains=keyword)
        )
    return queryset.order_by("-created_at", "-id")


def admin_review_payload(review: Review) -> dict:
    return {
        "public_id": review.public_id,
        "order_no": review.order.order_no,
        "user": {
            "public_id": review.user.public_id,
            "nickname": review.user.nickname,
            "username": review.user.username,
        },
        "product": {
            "public_id": review.product.public_id,
            "name": review.product.name,
        },
        "sku_spec": review.sku.spec_text,
        "rating": review.rating,
        "content": review.content,
        "status": review.status,
        "status_text": STATUS_TEXT.get(review.status, review.status),
        "reject_reason": review.reject_reason,
        "is_anonymous": review.is_anonymous,
        "images": [_image_payload(image) for image in review.images.all()],
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }
