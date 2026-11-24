"""下单链路压测：20 并发加购 → 创建订单 → 取消释放库存。"""

import uuid

from locust import between, task

from common import ApiUser


class OrderUser(ApiUser):
    wait_time = between(1, 2)

    @task
    def place_and_cancel(self) -> None:
        self.clear_cart()
        product = self.fetch_e2e_product()
        if not product or not product.get("skus"):
            return
        sku_id = product["skus"][0]["public_id"]
        cart = self.client.post(
            "/api/v1/cart/items/",
            json={"sku_public_id": sku_id, "quantity": 1},
            headers=self.headers,
            name="/cart/items/ [create]",
        )
        if cart.status_code not in (200, 201):
            return
        cart_item_id = cart.json()["public_id"]
        order = self.client.post(
            "/api/v1/orders/",
            json={
                "cart_item_public_ids": [cart_item_id],
                "address_public_id": getattr(self, "address_id", ""),
            },
            headers={
                **self.headers,
                "Idempotency-Key": f"perf-{uuid.uuid4().hex}",
            },
            name="/orders/ [create]",
        )
        if order.status_code != 201:
            return
        order_no = order.json()["order_no"]
        self.client.post(
            f"/api/v1/orders/{order_no}/cancel/",
            headers=self.headers,
            name="/orders/:order_no/cancel/",
        )
