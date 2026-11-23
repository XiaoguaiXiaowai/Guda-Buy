"""评价领域服务：资格校验、提交/重提、图片上传与后台审核的唯一写入口。"""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from apps.catalog import cache as catalog_cache
from apps.common.exceptions import BusinessError
from apps.orders.models import Order
from apps.reviews.models import Review, ReviewImage

logger = logging.getLogger("guda.reviews")

IMAGE_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
IMAGE_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
IMAGE_MAX_SIDE = 4096


def _audit(action: str, target, operator, detail: str = "") -> None:
    """后台操作审计：结构化日志记录操作人、对象与动作。"""
    logger.info(
        "reviews audit action=%s target=%s operator=%s detail=%s",
        action,
        getattr(target, "public_id", "-"),
        getattr(operator, "public_id", None),
        detail,
        extra={"action": action, "result": "ok"},
    )


def _notify_review_result(review: Review, *, approved: bool) -> None:
    """审核结果站内消息：经 notifications 服务写入，失败不影响评价审核主事务。"""
    try:
        from apps.notifications.services import create_notification

        if approved:
            title = "评价审核通过"
            content = f"你对订单 {review.order.order_no} 的评价已通过审核，感谢分享。"
        else:
            title = "评价审核未通过"
            reason = review.reject_reason or "不符合评价规范"
            content = (
                f"你对订单 {review.order.order_no} 的评价未通过审核，"
                f"原因：{reason}，可在订单详情重新提交。"
            )
        create_notification(
            review.user,
            notification_type="SYSTEM",
            title=title,
            content=content,
            biz_type="ORDER",
            biz_public_id=review.order.order_no,
        )
        logger.info(
            "评价审核结果已通知 result=%s review=%s",
            "APPROVED" if approved else "REJECTED",
            review.public_id,
            extra={"action": "reviews.notify_result", "result": "ok"},
        )
    except Exception:  # noqa: BLE001 - 通知失败不得影响评价审核
        logger.exception(
            "评价审核结果通知失败 review=%s",
            review.public_id,
            extra={"action": "reviews.notify_result", "result": "error"},
        )


def _contains_sensitive_words(content: str) -> bool:
    words = [word for word in getattr(settings, "REVIEW_SENSITIVE_WORDS", []) if word]
    return any(word in content for word in words)


def _review_order(user, order_no: str) -> Order:
    order = (
        Order.objects.filter(order_no=order_no, user=user, is_deleted=False)
        .select_related("review")
        .prefetch_related("items__sku__product")
        .first()
    )
    if order is None:
        raise BusinessError("ORDER_NOT_FOUND", "订单不存在", http_status=404)
    return order


def _pick_item(order: Order, sku_public_id: str = ""):
    items = list(order.items.select_related("sku__product").all())
    if not items:
        raise BusinessError("ORDER_NOT_FOUND", "订单商品不存在", http_status=404)

    if sku_public_id:
        for item in items:
            if item.sku.public_id == sku_public_id:
                return item
        raise BusinessError("COMMON_VALIDATION_ERROR", "该商品不属于此订单")

    if len(items) > 1:
        raise BusinessError("COMMON_VALIDATION_ERROR", "多商品订单请指定 sku_public_id")
    return items[0]


def _ensure_reviewable(order: Order) -> None:
    if order.status != Order.Status.COMPLETED:
        raise BusinessError("REVIEW_ORDER_NOT_COMPLETED", "订单未完成，不可评价", http_status=422)
    deadline = (
        order.completed_at + timedelta(days=settings.REVIEW_WINDOW_DAYS)
        if order.completed_at
        else None
    )
    if deadline is None or timezone.now() > deadline:
        raise BusinessError(
            "REVIEW_WINDOW_EXPIRED",
            f"已超过 {settings.REVIEW_WINDOW_DAYS} 天评价期限",
            http_status=422,
        )


def get_order_review_state(user, order_no: str):
    """返回订单与当前评价（可为空），供接口层组装可评状态。"""
    order = _review_order(user, order_no)
    review = Review.objects.filter(order=order, is_deleted=False).first()
    return order, review


@transaction.atomic
def submit_review(user, order_no: str, data: dict) -> tuple[Review, bool]:
    """提交评价：一单一评；已驳回时覆盖原记录并回到待审核。"""
    order = (
        Order.objects.select_for_update()
        .filter(order_no=order_no, user=user, is_deleted=False)
        .first()
    )
    if order is None:
        raise BusinessError("ORDER_NOT_FOUND", "订单不存在", http_status=404)

    _ensure_reviewable(order)
    item = _pick_item(order, data.get("sku_public_id", ""))
    existing = Review.objects.select_for_update().filter(order=order, is_deleted=False).first()

    if existing is not None and existing.status != Review.Status.REJECTED:
        raise BusinessError("REVIEW_ALREADY_EXISTS", "该订单已评价", http_status=409)

    content = data["content"].strip()
    if _contains_sensitive_words(content):
        logger.warning(
            "评价命中敏感词，转人工审核 review_order=%s",
            order.order_no,
            extra={"action": "reviews.sensitive_hit", "result": "manual"},
        )

    if existing is not None:
        existing.product = item.sku.product
        existing.sku = item.sku
        existing.rating = data["rating"]
        existing.content = content
        existing.is_anonymous = data.get("is_anonymous", False)
        existing.status = Review.Status.PENDING
        existing.reject_reason = ""
        existing.save(
            update_fields=[
                "product",
                "sku",
                "rating",
                "content",
                "is_anonymous",
                "status",
                "reject_reason",
                "updated_at",
            ]
        )
        _audit("reviews.resubmit", existing, user, "驳回后重新提交")
        return existing, False

    try:
        review = Review.objects.create(
            order=order,
            user=user,
            product=item.sku.product,
            sku=item.sku,
            rating=data["rating"],
            content=content,
            is_anonymous=data.get("is_anonymous", False),
        )
    except IntegrityError as exc:  # 并发重复提交兜底，唯一约束保证一单一评
        raise BusinessError("REVIEW_ALREADY_EXISTS", "该订单已评价", http_status=409) from exc
    _audit("reviews.submit", review, user, f"rating={review.rating}")
    return review, True


def _validate_image(uploaded_file) -> str:
    filename = uploaded_file.name or ""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in IMAGE_ALLOWED_EXTENSIONS:
        raise BusinessError("COMMON_VALIDATION_ERROR", "仅支持 jpg/jpeg/png/webp 格式图片")
    if (uploaded_file.content_type or "") not in IMAGE_ALLOWED_CONTENT_TYPES:
        raise BusinessError("COMMON_VALIDATION_ERROR", "图片 MIME 类型不合法")
    if uploaded_file.size > settings.REVIEW_IMAGE_MAX_BYTES:
        raise BusinessError("COMMON_VALIDATION_ERROR", "图片不能超过 5MB")

    try:
        image = Image.open(uploaded_file)
        image.verify()
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        width, height = image.size
        uploaded_file.seek(0)
    except (UnidentifiedImageError, OSError) as exc:
        raise BusinessError("COMMON_VALIDATION_ERROR", "图片文件已损坏或格式不正确") from exc

    if width > IMAGE_MAX_SIDE or height > IMAGE_MAX_SIDE:
        raise BusinessError("COMMON_VALIDATION_ERROR", "图片尺寸不能超过 4096px")
    return "jpg" if extension == "jpeg" else extension


@transaction.atomic
def add_review_image(user, review_public_id: str, uploaded_file) -> ReviewImage:
    """上传评价图片：仅本人、最多 3 张、审核通过后不可再修改。"""
    review = (
        Review.objects.select_for_update()
        .filter(public_id=review_public_id, user=user, is_deleted=False)
        .first()
    )
    if review is None:
        raise BusinessError("REVIEW_NOT_FOUND", "评价不存在", http_status=404)
    if review.status == Review.Status.APPROVED:
        raise BusinessError("REVIEW_STATUS_CONFLICT", "已通过审核的评价不可修改", http_status=409)

    current = review.images.count()
    if current >= settings.REVIEW_MAX_IMAGES:
        raise BusinessError(
            "REVIEW_IMAGE_LIMIT",
            f"最多上传 {settings.REVIEW_MAX_IMAGES} 张图片",
            http_status=422,
        )

    suffix = _validate_image(uploaded_file)
    content = uploaded_file.read()
    relative_path = f"reviews/{review.public_id}/{secrets.token_hex(8)}.{suffix}"
    saved_path = default_storage.save(relative_path, ContentFile(content))

    image = ReviewImage.objects.create(review=review, image=saved_path, sort_order=current + 1)
    _audit("reviews.upload_image", review, user, saved_path)
    return image


def _get_review_for_audit(public_id: str, *, lock: bool = False) -> Review:
    queryset = Review.objects.select_related("user", "product", "sku", "order")
    if lock:
        queryset = queryset.select_for_update()
    review = queryset.filter(public_id=public_id, is_deleted=False).first()
    if review is None:
        raise BusinessError("REVIEW_NOT_FOUND", "评价不存在", http_status=404)
    return review


def approve_review(operator, public_id: str) -> Review:
    """审核通过：仅 PENDING 可流转，并失效商品详情缓存以更新评分聚合。"""
    with transaction.atomic():
        review = _get_review_for_audit(public_id, lock=True)
        if review.status != Review.Status.PENDING:
            raise BusinessError("REVIEW_STATUS_CONFLICT", "仅待审核评价可审核", http_status=409)
        review.status = Review.Status.APPROVED
        review.reject_reason = ""
        review.save(update_fields=["status", "reject_reason", "updated_at"])
        transaction.on_commit(catalog_cache.bump_product_version)
        transaction.on_commit(lambda: _notify_review_result(review, approved=True))
        _audit("reviews.approve", review, operator)
    return review


def reject_review(operator, public_id: str, reject_reason: str) -> Review:
    """审核驳回：必须填写原因，并失效商品详情缓存。"""
    reason = (reject_reason or "").strip()
    if not reason:
        raise BusinessError("COMMON_VALIDATION_ERROR", "驳回必须填写原因")
    if len(reason) > 100:
        raise BusinessError("COMMON_VALIDATION_ERROR", "驳回原因不能超过 100 字")

    with transaction.atomic():
        review = _get_review_for_audit(public_id, lock=True)
        if review.status != Review.Status.PENDING:
            raise BusinessError("REVIEW_STATUS_CONFLICT", "仅待审核评价可审核", http_status=409)
        review.status = Review.Status.REJECTED
        review.reject_reason = reason
        review.save(update_fields=["status", "reject_reason", "updated_at"])
        transaction.on_commit(catalog_cache.bump_product_version)
        transaction.on_commit(lambda: _notify_review_result(review, approved=False))
        _audit("reviews.reject", review, operator, reason)
    return review
