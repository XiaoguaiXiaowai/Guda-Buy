import io

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.reviews.models import Review, ReviewImage

IMAGE_URL = "/api/v1/reviews/{public_id}/images/"
PNG_MIME = "image/png"


def _png_bytes(width: int = 10, height: int = 10) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=(200, 120, 90)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_upload_image_success(auth_client, review, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path

    response = auth_client.post(
        IMAGE_URL.format(public_id=review.public_id),
        {"file": SimpleUploadedFile("detail.png", _png_bytes(), content_type=PNG_MIME)},
        format="multipart",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["image"].startswith(f"reviews/{review.public_id}/")
    assert body["sort_order"] == 1
    assert review.images.count() == 1
    assert (tmp_path / body["image"]).exists()


def test_review_image_limit(auth_client, review):
    for index in range(3):
        ReviewImage.objects.create(review=review, image=f"reviews/{review.public_id}/{index}.png")

    response = auth_client.post(
        IMAGE_URL.format(public_id=review.public_id),
        {"file": SimpleUploadedFile("fourth.png", _png_bytes(), content_type=PNG_MIME)},
        format="multipart",
    )

    assert response.status_code == 422
    assert response.json()["code"] == "REVIEW_IMAGE_LIMIT"
    assert review.images.count() == 3


def test_upload_rejects_invalid_files(auth_client, review, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    url = IMAGE_URL.format(public_id=review.public_id)

    wrong_extension = auth_client.post(
        url,
        {"file": SimpleUploadedFile("shell.exe", b"MZ", content_type="application/octet-stream")},
        format="multipart",
    )
    assert wrong_extension.status_code == 400

    wrong_mime = auth_client.post(
        url,
        {"file": SimpleUploadedFile("detail.png", _png_bytes(), content_type="image/gif")},
        format="multipart",
    )
    assert wrong_mime.status_code == 400

    corrupt = auth_client.post(
        url,
        {"file": SimpleUploadedFile("broken.png", b"not-an-image", content_type=PNG_MIME)},
        format="multipart",
    )
    assert corrupt.status_code == 400


def test_upload_rejects_oversize_and_huge_dimensions(auth_client, review, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    url = IMAGE_URL.format(public_id=review.public_id)

    oversize = auth_client.post(
        url,
        {
            "file": SimpleUploadedFile(
                "big.png",
                b"0" * (settings.REVIEW_IMAGE_MAX_BYTES + 1),
                content_type=PNG_MIME,
            )
        },
        format="multipart",
    )
    assert oversize.status_code == 400

    huge = auth_client.post(
        url,
        {
            "file": SimpleUploadedFile(
                "huge.png", _png_bytes(width=4097, height=8), content_type=PNG_MIME
            )
        },
        format="multipart",
    )
    assert huge.status_code == 400


def test_only_owner_can_upload(other_client, review, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path

    response = other_client.post(
        IMAGE_URL.format(public_id=review.public_id),
        {"file": SimpleUploadedFile("detail.png", _png_bytes(), content_type=PNG_MIME)},
        format="multipart",
    )

    assert response.status_code == 404


def test_approved_review_is_immutable(auth_client, user, completed_order, sku, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    from apps.reviews.tests.conftest import make_review

    approved = make_review(user, completed_order, sku, status=Review.Status.APPROVED)

    response = auth_client.post(
        IMAGE_URL.format(public_id=approved.public_id),
        {"file": SimpleUploadedFile("detail.png", _png_bytes(), content_type=PNG_MIME)},
        format="multipart",
    )

    assert response.status_code == 409
    assert response.json()["code"] == "REVIEW_STATUS_CONFLICT"
