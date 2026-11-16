import io
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.catalog import services
from apps.catalog.models import Category, Product, Sku, StockLog
from apps.catalog.tests.conftest import make_product, make_sku, png_upload
from apps.common.exceptions import BusinessError

pytestmark = pytest.mark.django_db


def _product_url(name, public_id):
    return reverse(f"catalog:{name}", args=[public_id])


def test_operator_creates_draft_product(operator_client, child_category):
    response = operator_client.post(
        reverse("catalog:admin-product-list"),
        {
            "category_public_id": child_category.public_id,
            "name": "法式碎花连衣裙",
            "subtitle": "春季新品",
            "description": "柔软面料",
        },
        format="json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == Product.Status.DRAFT
    assert body["category"]["public_id"] == child_category.public_id
    assert body["sku_count"] == 0


def test_customer_cannot_create_product(client, customer, child_category):
    client.force_authenticate(user=customer)
    response = client.post(
        reverse("catalog:admin-product-list"),
        {"category_public_id": child_category.public_id, "name": "越权商品"},
        format="json",
    )
    assert response.status_code == 403
    assert response.json()["code"] == "COMMON_PERMISSION_DENIED"


def test_anonymous_admin_api_returns_401(client, child_category):
    response = client.get(reverse("catalog:admin-product-list"))
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_TOKEN_INVALID"


def test_publish_requires_on_sale_sku(operator_client, child_category):
    product = make_product(child_category, status=Product.Status.DRAFT)
    response = operator_client.post(_product_url("admin-product-publish", product.public_id))

    assert response.status_code == 422
    assert response.json()["code"] == "PRODUCT_NO_SKU"


def test_publish_computes_price_range_and_unpublish_hides_detail(
    operator_client, client, child_category
):
    product = make_product(child_category, status=Product.Status.DRAFT)
    make_sku(product, sku_code="DRESS-001", sale_price="99.00")
    make_sku(product, sku_code="DRESS-002", sale_price="129.00", spec_text="米白 / L")

    publish = operator_client.post(_product_url("admin-product-publish", product.public_id))
    assert publish.status_code == 200
    assert publish.json()["status"] == Product.Status.ON_SALE
    assert publish.json()["price_min"] == "99.00"
    assert publish.json()["price_max"] == "129.00"

    assert client.get(_product_url("product-detail", product.public_id)).status_code == 200

    unpublish = operator_client.post(_product_url("admin-product-unpublish", product.public_id))
    assert unpublish.status_code == 200
    assert unpublish.json()["status"] == Product.Status.OFF_SALE
    assert client.get(_product_url("product-detail", product.public_id)).status_code == 404


def test_unpublish_draft_is_conflict(operator_client, child_category):
    product = make_product(child_category, status=Product.Status.DRAFT)
    response = operator_client.post(_product_url("admin-product-unpublish", product.public_id))
    assert response.status_code == 409
    assert response.json()["code"] == "PRODUCT_STATUS_CONFLICT"


def test_sku_code_validation_and_uniqueness(operator_client, product, sku):
    invalid = operator_client.post(
        _product_url("admin-sku-list", product.public_id),
        {"sku_code": "bad", "spec_text": "黑色 / M", "sale_price": "10.00"},
        format="json",
    )
    assert invalid.status_code == 400

    duplicated = operator_client.post(
        _product_url("admin-sku-list", product.public_id),
        {"sku_code": "DRESS-001", "spec_text": "黑色 / M", "sale_price": "10.00"},
        format="json",
    )
    assert duplicated.status_code == 409
    assert duplicated.json()["code"] == "PRODUCT_SKU_CODE_EXISTS"


def test_sku_price_update_refreshes_product_price_range(operator_client, product, sku):
    response = operator_client.put(
        _product_url("admin-sku-detail", sku.public_id),
        {"sale_price": "88.00"},
        format="json",
    )

    assert response.status_code == 200
    product.refresh_from_db()
    assert product.price_min == Decimal("88.00")
    assert product.price_max == Decimal("88.00")


def test_last_on_sale_sku_cannot_be_disabled(operator_client, product, sku):
    response = operator_client.put(
        _product_url("admin-sku-detail", sku.public_id),
        {"status": Sku.Status.OFF_SALE},
        format="json",
    )
    assert response.status_code == 409
    assert response.json()["code"] == "PRODUCT_STATUS_CONFLICT"


def test_stock_adjust_records_log_and_operator(operator_client, operator, sku):
    response = operator_client.patch(
        _product_url("admin-sku-stock", sku.public_id),
        {"change": 15, "reason": "供应商补货"},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["stock"] == 25
    log = StockLog.objects.get(sku=sku)
    assert (log.change, log.stock_before, log.stock_after) == (15, 10, 25)
    assert log.operator_id == operator.id
    assert log.reason == "供应商补货"


def test_stock_adjust_rejects_non_positive_and_over_capacity(operator_client, sku):
    negative = operator_client.patch(
        _product_url("admin-sku-stock", sku.public_id), {"change": -1}, format="json"
    )
    assert negative.status_code == 400

    over = operator_client.patch(
        _product_url("admin-sku-stock", sku.public_id), {"change": 95}, format="json"
    )
    assert over.status_code == 422
    assert over.json()["code"] == "PRODUCT_STOCK_INVALID"


def test_soft_deleted_product_disappears_from_admin_list(operator_client, product, sku):
    response = operator_client.delete(_product_url("admin-product-detail", product.public_id))
    assert response.status_code == 204

    listing = operator_client.get(reverse("catalog:admin-product-list"))
    assert listing.json()["count"] == 0
    assert Product.objects.get(pk=product.pk).is_deleted is True


def test_image_upload_sets_main_image(operator_client, product):
    response = operator_client.post(
        _product_url("admin-product-image-upload", product.public_id),
        {"file": png_upload()},
        format="multipart",
    )

    assert response.status_code == 201
    product.refresh_from_db()
    assert product.main_image.startswith(f"products/{product.public_id}/")
    assert product.images.count() == 1


def test_image_upload_rejects_gif(operator_client, product):
    payload = png_upload(name="cover.gif")
    response = operator_client.post(
        _product_url("admin-product-image-upload", product.public_id),
        {"file": payload},
        format="multipart",
    )

    assert response.status_code == 400
    assert product.images.count() == 0


def test_update_product_changes_fields_and_category(operator_client, operator, product):
    other = Category.objects.create(name="半身裙", parent=product.category.parent)

    response = operator_client.put(
        _product_url("admin-product-detail", product.public_id),
        {
            "name": "法式方领连衣裙",
            "subtitle": "新副标题",
            "category_public_id": other.public_id,
        },
        format="json",
    )

    assert response.status_code == 200
    product.refresh_from_db()
    assert product.name == "法式方领连衣裙"
    assert product.subtitle == "新副标题"
    assert product.category_id == other.id
    assert product.updated_by_id == operator.id

    invalid = operator_client.put(
        _product_url("admin-product-detail", product.public_id),
        {"name": "一"},
        format="json",
    )
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "COMMON_VALIDATION_ERROR"


def test_admin_product_detail_returns_404_when_missing(operator_client):
    response = operator_client.get(_product_url("admin-product-detail", "no-such-product"))
    assert response.status_code == 404
    assert response.json()["code"] == "PRODUCT_NOT_FOUND"


def test_publish_is_idempotent(operator_client, product, sku):
    first = operator_client.post(_product_url("admin-product-publish", product.public_id))
    assert first.status_code == 200

    second = operator_client.post(_product_url("admin-product-publish", product.public_id))
    assert second.status_code == 200
    assert second.json()["status"] == Product.Status.ON_SALE


def test_create_sku_rejects_over_capacity(operator_client, product):
    response = operator_client.post(
        _product_url("admin-sku-list", product.public_id),
        {
            "sku_code": "DRESS-009",
            "spec_text": "黑色 / L",
            "sale_price": "99.00",
            "stock": 60,
            "stock_capacity": 50,
        },
        format="json",
    )

    assert response.status_code == 422
    assert response.json()["code"] == "PRODUCT_STOCK_INVALID"


def test_update_sku_rejects_duplicate_code_and_over_capacity(operator_client, product, sku):
    make_sku(product, sku_code="DRESS-002", spec_text="米白 / L")

    duplicated = operator_client.put(
        _product_url("admin-sku-detail", sku.public_id),
        {"sku_code": "DRESS-002"},
        format="json",
    )
    assert duplicated.status_code == 409
    assert duplicated.json()["code"] == "PRODUCT_SKU_CODE_EXISTS"

    over = operator_client.put(
        _product_url("admin-sku-detail", sku.public_id),
        {"stock": 200},
        format="json",
    )
    assert over.status_code == 422
    assert over.json()["code"] == "PRODUCT_STOCK_INVALID"


def test_stock_adjust_service_rejects_non_positive_and_unknown_sku(sku):
    with pytest.raises(BusinessError) as invalid:
        services.adjust_stock(sku.public_id, 0)
    assert invalid.value.code == "PRODUCT_STOCK_INVALID"

    with pytest.raises(BusinessError) as missing:
        services.adjust_stock("no-such-sku", 1)
    assert missing.value.code == "PRODUCT_SKU_NOT_FOUND"


def _png_file(name: str, size: tuple[int, int] = (10, 10)) -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(255, 255, 255)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def test_image_upload_rejects_bad_mime_oversize_broken_and_large_side(operator_client, product):
    url = _product_url("admin-product-image-upload", product.public_id)

    bad_mime = SimpleUploadedFile("cover.png", _png_file("cover.png").read(), "image/gif")
    assert operator_client.post(url, {"file": bad_mime}, format="multipart").status_code == 400

    oversize = SimpleUploadedFile("big.png", b"0" * (5 * 1024 * 1024 + 1), "image/png")
    assert operator_client.post(url, {"file": oversize}, format="multipart").status_code == 400

    broken = SimpleUploadedFile("broken.png", b"not-an-image", "image/png")
    assert operator_client.post(url, {"file": broken}, format="multipart").status_code == 400

    large_side = _png_file("large.png", size=(4097, 1))
    assert operator_client.post(url, {"file": large_side}, format="multipart").status_code == 400
    assert product.images.count() == 0


def test_delete_product_image_falls_back_to_next_main_image(operator_client, product):
    url = _product_url("admin-product-image-upload", product.public_id)
    first = operator_client.post(url, {"file": png_upload("first.png")}, format="multipart").json()
    second_response = operator_client.post(
        url, {"file": png_upload("second.png")}, format="multipart"
    )
    second = second_response.json()

    product.refresh_from_db()
    assert product.main_image == first["image"]

    delete_url = reverse(
        "catalog:admin-product-image-delete",
        args=[product.public_id, first["public_id"]],
    )
    assert operator_client.delete(delete_url).status_code == 204

    product.refresh_from_db()
    assert product.main_image == second["image"]
    assert product.images.count() == 1

    missing = reverse(
        "catalog:admin-product-image-delete",
        args=[product.public_id, first["public_id"]],
    )
    assert operator_client.delete(missing).status_code == 404
