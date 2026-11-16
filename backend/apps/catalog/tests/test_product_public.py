from decimal import Decimal

import pytest
from django.urls import reverse

from apps.catalog import services
from apps.catalog.models import Product, Sku
from apps.catalog.tests.conftest import make_product, make_sku

pytestmark = pytest.mark.django_db


def _list(client, **params):
    return client.get(reverse("catalog:product-list"), params)


def test_list_only_returns_on_sale_products(client, child_category):
    make_product(child_category, name="在售商品")
    make_product(child_category, name="草稿商品", status=Product.Status.DRAFT)
    make_product(child_category, name="下架商品", status=Product.Status.OFF_SALE)
    make_product(child_category, name="已删除商品").soft_delete()

    body = _list(client).json()

    assert body["count"] == 1
    assert [item["name"] for item in body["results"]] == ["在售商品"]


def test_parent_category_filter_includes_children(client, parent_category, child_category):
    sibling = parent_category.children.create(name="半身裙", sort_weight=2)
    make_product(child_category, name="连衣裙")
    make_product(sibling, name="半身裙商品")

    body = _list(client, category=parent_category.public_id).json()
    assert {item["name"] for item in body["results"]} == {"连衣裙", "半身裙商品"}

    child_body = _list(client, category=child_category.public_id).json()
    assert [item["name"] for item in child_body["results"]] == ["连衣裙"]


def test_price_range_and_keyword_filters(client, child_category):
    make_product(child_category, name="法式碎花连衣裙", price_min=Decimal("59.00"))
    make_product(child_category, name="通勤西装连衣裙", price_min=Decimal("199.00"))

    price_body = _list(client, price_min="100", price_max="300").json()
    assert [item["name"] for item in price_body["results"]] == ["通勤西装连衣裙"]

    search_body = _list(client, search="法式").json()
    assert [item["name"] for item in search_body["results"]] == ["法式碎花连衣裙"]


def test_ordering_whitelist_and_fallback(client, child_category):
    make_product(child_category, name="高价", price_min=Decimal("300.00"))
    make_product(child_category, name="低价", price_min=Decimal("99.00"))

    ascending = _list(client, ordering="price").json()
    assert [item["name"] for item in ascending["results"]] == ["低价", "高价"]

    descending = _list(client, ordering="-price").json()
    assert [item["name"] for item in descending["results"]] == ["高价", "低价"]

    injected = _list(client, ordering="price;drop table").json()
    assert injected["count"] == 2


def test_pagination_metadata(client, child_category):
    for index in range(5):
        make_product(child_category, name=f"商品{index}")

    body = _list(client, page=2, page_size=2).json()

    assert body["count"] == 5
    assert body["page"] == 2
    assert body["page_size"] == 2
    assert body["total_pages"] == 3
    assert len(body["results"]) == 2


def test_detail_includes_only_on_sale_skus_with_stock_text(client, product):
    make_sku(product, sku_code="DRESS-001", stock=3)
    make_sku(product, sku_code="DRESS-002", stock=0)
    make_sku(product, sku_code="DRESS-003", stock=30, status=Sku.Status.OFF_SALE)

    response = client.get(reverse("catalog:product-detail", args=[product.public_id]))

    assert response.status_code == 200
    body = response.json()
    assert len(body["skus"]) == 2
    texts = {item["sku_code"]: item["stock_text"] for item in body["skus"]}
    assert texts == {"DRESS-001": "仅剩 3 件", "DRESS-002": "缺货"}
    assert body["review_summary"]["count"] == 0


def test_detail_of_off_sale_product_returns_404(client, child_category):
    product = make_product(child_category, status=Product.Status.OFF_SALE)
    response = client.get(reverse("catalog:product-detail", args=[product.public_id]))

    assert response.status_code == 404
    assert response.json()["code"] == "PRODUCT_NOT_FOUND"


def test_detail_is_cached_and_invalidated_by_sku_price(
    client, product, sku, django_assert_num_queries
):
    url = reverse("catalog:product-detail", args=[product.public_id])
    assert client.get(url).json()["price_min"] == "99.00"

    with django_assert_num_queries(0):
        assert client.get(url).json()["price_min"] == "99.00"

    services.update_sku(sku.public_id, {"sale_price": Decimal("88.00")})
    updated = client.get(url).json()
    assert updated["price_min"] == "88.00"


def test_related_products_same_category_excludes_self(client, product, child_category):
    make_product(child_category, name="同类热销", sales_count=100)
    other = child_category.parent.children.create(name="半身裙")
    make_product(other, name="其他分类")

    body = client.get(reverse("catalog:product-related", args=[product.public_id])).json()

    assert [item["name"] for item in body] == ["同类热销"]


def test_suggest_limits_to_ten_and_prioritizes_prefix(client, child_category):
    for index in range(12):
        make_product(child_category, name=f"连衣裙{index}")
    make_product(child_category, name="春季连衣裙")

    body = client.get(reverse("catalog:product-suggest"), {"keyword": "连衣裙"}).json()

    assert len(body) == 10
    assert all("连衣裙" in item["name"] for item in body)
