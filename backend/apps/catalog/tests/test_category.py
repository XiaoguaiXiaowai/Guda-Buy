import pytest
from django.urls import reverse

from apps.catalog import services
from apps.catalog.models import Category
from apps.catalog.tests.conftest import make_product
from apps.common.exceptions import BusinessError

pytestmark = pytest.mark.django_db


def test_category_tree_returns_two_levels_with_on_sale_counts(
    client, parent_category, child_category, product
):
    make_product(child_category, name="草稿商品", status="DRAFT")

    response = client.get(reverse("catalog:category-tree"))

    assert response.status_code == 200
    tree = response.json()
    assert len(tree) == 1
    assert tree[0]["name"] == "女装"
    assert tree[0]["product_count"] == 1
    child = tree[0]["children"][0]
    assert child["name"] == "连衣裙"
    assert child["product_count"] == 1


def test_category_tree_is_cached(
    client, parent_category, child_category, django_assert_num_queries
):
    assert client.get(reverse("catalog:category-tree")).status_code == 200
    with django_assert_num_queries(0):
        assert client.get(reverse("catalog:category-tree")).status_code == 200


def test_category_create_rejects_third_level(operator_client, parent_category, child_category):
    response = operator_client.post(
        reverse("catalog:admin-category-list"),
        {"name": "短款", "parent_public_id": child_category.public_id},
        format="json",
    )

    assert response.status_code == 422
    assert response.json()["code"] == "PRODUCT_CATEGORY_INVALID"


def test_category_create_requires_operator(customer, client):
    client.force_authenticate(user=customer)
    response = client.post(reverse("catalog:admin-category-list"), {"name": "男装"}, format="json")
    assert response.status_code == 403


def test_category_delete_blocked_when_products_exist(operator_client, child_category, product):
    response = operator_client.delete(
        reverse("catalog:admin-category-detail", args=[child_category.public_id])
    )

    assert response.status_code == 409
    assert response.json()["code"] == "PRODUCT_CATEGORY_NOT_EMPTY"


def test_category_delete_blocked_when_children_exist(
    operator_client, parent_category, child_category
):
    response = operator_client.delete(
        reverse("catalog:admin-category-detail", args=[parent_category.public_id])
    )
    assert response.status_code == 409


def test_empty_child_category_can_be_deleted(operator_client, child_category):
    response = operator_client.delete(
        reverse("catalog:admin-category-detail", args=[child_category.public_id])
    )

    assert response.status_code == 204
    assert Category.objects.get(pk=child_category.pk).is_deleted is True


def test_category_update_refreshes_tree_cache(operator_client, parent_category, child_category):
    tree_url = reverse("catalog:category-tree")
    assert operator_client.get(tree_url).json()[0]["children"][0]["name"] == "连衣裙"

    response = operator_client.put(
        reverse("catalog:admin-category-detail", args=[child_category.public_id]),
        {"name": "长裙"},
        format="json",
    )
    assert response.status_code == 200
    assert operator_client.get(tree_url).json()[0]["children"][0]["name"] == "长裙"


def test_product_requires_leaf_category(operator_client, parent_category, sku):
    response = operator_client.post(
        reverse("catalog:admin-product-list"),
        {"category_public_id": parent_category.public_id, "name": "测试商品"},
        format="json",
    )

    assert response.status_code == 422
    assert response.json()["code"] == "PRODUCT_CATEGORY_INVALID"


def test_create_category_then_update_sort_weight(operator_client):
    created = operator_client.post(
        reverse("catalog:admin-category-list"),
        {"name": "男装", "sort_weight": 5},
        format="json",
    )
    assert created.status_code == 201
    body = created.json()
    assert body["level"] == 1
    assert body["product_count"] == 0

    updated = operator_client.put(
        reverse("catalog:admin-category-detail", args=[body["public_id"]]),
        {"sort_weight": 99},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["sort_weight"] == 99


def test_category_service_rejects_blank_name_and_missing_category():
    with pytest.raises(BusinessError) as create_error:
        services.create_category(name="   ")
    assert create_error.value.code == "COMMON_VALIDATION_ERROR"

    with pytest.raises(BusinessError) as update_error:
        services.update_category("no-such-category", {"name": ""})
    assert update_error.value.code == "PRODUCT_CATEGORY_NOT_FOUND"
