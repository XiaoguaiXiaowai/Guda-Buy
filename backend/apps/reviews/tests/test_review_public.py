import pytest

from apps.reviews import selectors
from apps.reviews.models import Review
from apps.reviews.tests.conftest import build_order, make_review

LIST_URL = "/api/v1/products/{public_id}/reviews/"


def _approved(user, address, sku, **kwargs):
    order = build_order(user, address, sku)
    return make_review(user, order, sku, status=Review.Status.APPROVED, **kwargs)


def test_only_approved_reviews_are_public(client, user, address, sku):
    _approved(user, address, sku, content="通过审核的评价内容")
    pending_order = build_order(user, address, sku)
    make_review(user, pending_order, sku, content="待审核的评价内容")
    rejected_order = build_order(user, address, sku)
    make_review(user, rejected_order, sku, status=Review.Status.REJECTED, content="驳回的评价内容")

    body = client.get(LIST_URL.format(public_id=sku.product.public_id)).json()

    assert body["count"] == 1
    assert body["results"][0]["content"] == "通过审核的评价内容"


def test_anonymous_review_masks_nickname(client, user, address, sku):
    _approved(user, address, sku, is_anonymous=True)

    item = client.get(LIST_URL.format(public_id=sku.product.public_id)).json()["results"][0]

    assert item["display_name"] == "张**"
    assert item["avatar"] == ""
    assert "username" not in item


def test_non_anonymous_review_shows_nickname(client, user, address, sku):
    _approved(user, address, sku, is_anonymous=False)

    item = client.get(LIST_URL.format(public_id=sku.product.public_id)).json()["results"][0]

    assert item["display_name"] == "张小明"
    assert "username" not in item


def test_review_list_pagination(client, user, address, sku):
    _approved(user, address, sku)
    _approved(user, address, sku)

    body = client.get(
        LIST_URL.format(public_id=sku.product.public_id), {"page_size": 1, "page": 2}
    ).json()

    assert body["count"] == 2
    assert len(body["results"]) == 1


@pytest.mark.django_db
def test_missing_product_returns_404(client):
    response = client.get(LIST_URL.format(public_id="missing"))
    assert response.status_code == 404
    assert response.json()["code"] == "PRODUCT_NOT_FOUND"


def test_review_summary_aggregation_v9_7(user, address, sku):
    for rating in (5, 5, 5, 3):
        _approved(user, address, sku, rating=rating)

    summary = selectors.review_summary(sku.product_id)

    assert summary["count"] == 4
    assert summary["average"] == "4.5"
    assert summary["distribution"] == {"5": 3, "4": 0, "3": 1, "2": 0, "1": 0}


def test_review_list_query_budget(client, user, address, sku, django_assert_num_queries):
    for _ in range(2):
        _approved(user, address, sku)
    url = LIST_URL.format(public_id=sku.product.public_id)

    with django_assert_num_queries(4):
        assert client.get(url).status_code == 200


def test_product_detail_exposes_real_summary(client, user, address, sku):
    _approved(user, address, sku, rating=5)

    body = client.get(f"/api/v1/products/{sku.product.public_id}/").json()

    assert body["review_summary"]["count"] == 1
    assert body["review_summary"]["average"] == "5.0"
