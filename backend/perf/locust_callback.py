"""支付回调压测：10 并发创建订单 → 模拟支付 → 回调成功。"""

import uuid

from locust import between, task

from common import ApiUser


class CallbackUser(ApiUser):
    wait_time = between(1, 2)

    @task
    def pay_and_callback(self) -> None:
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
        order = self.client.post(
            "/api/v1/orders/",
            json={
                "cart_item_public_ids": [cart.json()["public_id"]],
                "address_public_id": getattr(self, "address_id", ""),
            },
            headers={**self.headers, "Idempotency-Key": f"perf-{uuid.uuid4().hex}"},
            name="/orders/ [create]",
        )
        if order.status_code != 201:
            return
        order_no = order.json()["order_no"]
        cashier = self.client.post(
            f"/api/v1/payments/{order_no}/mock-pay/",
            json={"channel": "ALIPAY_MOCK"},
            headers=self.headers,
            name="/payments/:order_no/mock-pay/",
        )
        if cashier.status_code != 200:
            return
        body = cashier.json()
        self.client.post(
            "/api/v1/payments/callback/",
            json={
                "payment_no": body["payment_no"],
                "amount": body["amount"],
                "status": "SUCCESS",
                "signature": body["sign"],
                "transaction_ref": f"perf-{uuid.uuid4().hex[:12]}",
            },
            headers=self.headers,
            name="/payments/callback/",
        )
