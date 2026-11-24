"""读接口压测：50 并发读取商品列表/详情/评价/分类。"""

from locust import between, task

from common import ApiUser


class ReadUser(ApiUser):
    wait_time = between(1, 2)

    def on_start(self) -> None:
        self.headers = {}
        response = self.client.post(
            "/api/v1/auth/login/",
            json={"account": "e2e_buyer", "password": "Passw0rd123"},
            name="/auth/login/",
        )
        if response.status_code == 200:
            self.headers = {"Authorization": f"Bearer {response.json()['access']}"}
        product = self.fetch_e2e_product()
        self.product_id = product["public_id"] if product else ""

    @task(6)
    def product_list(self) -> None:
        self.client.get("/api/v1/products/?page=1&page_size=12", name="/products/")

    @task(3)
    def product_detail(self) -> None:
        if self.product_id:
            self.client.get(f"/api/v1/products/{self.product_id}/", name="/products/:id/")

    @task(2)
    def product_reviews(self) -> None:
        if self.product_id:
            self.client.get(
                f"/api/v1/products/{self.product_id}/reviews/?page=1&page_size=5",
                name="/products/:id/reviews/",
            )

    @task(2)
    def category_tree(self) -> None:
        self.client.get("/api/v1/categories/tree/", name="/categories/tree/")

    @task(1)
    def unread_count(self) -> None:
        self.client.get(
            "/api/v1/notifications/unread-count/",
            headers=self.headers,
            name="/notifications/unread-count/",
        )
