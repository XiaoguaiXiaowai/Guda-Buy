"""Locust 公共逻辑：账号池、登录、地址与购物车准备。"""

import itertools
import threading

from locust import HttpUser, between

PASSWORD = "Passw0rd123"
PERF_ACCOUNTS = [f"e2e_perf{index:02d}" for index in range(1, 21)]

_counter = itertools.count()
_lock = threading.Lock()


def next_account() -> str:
    with _lock:
        return PERF_ACCOUNTS[next(_counter) % len(PERF_ACCOUNTS)]


class ApiUser(HttpUser):
    """带登录态的抽象用户。"""

    abstract = True
    wait_time = between(1, 2)

    def on_start(self) -> None:
        self.account = next_account()
        self.headers: dict[str, str] = {}
        response = self.client.post(
            "/api/v1/auth/login/",
            json={"account": self.account, "password": PASSWORD},
            name="/auth/login/",
        )
        if response.status_code == 200:
            self.headers = {"Authorization": f"Bearer {response.json()['access']}"}
        self.ensure_address()
        self.clear_cart()

    def ensure_address(self) -> None:
        response = self.client.get(
            "/api/v1/users/me/addresses/", headers=self.headers, name="/users/me/addresses/"
        )
        if response.status_code == 200:
            body = response.json()
            items = body if isinstance(body, list) else body.get("results", [])
            if items:
                self.address_id = items[0]["public_id"]
                return
        suffix = self.account[-2:]
        created = self.client.post(
            "/api/v1/users/me/addresses/",
            json={
                "receiver_name": "压测收货人",
                "phone": f"1380000{suffix}00",
                "province": "广东省",
                "city": "深圳市",
                "district": "南山区",
                "detail": "压测路 1 号",
                "postal_code": "518000",
            },
            headers=self.headers,
            name="/users/me/addresses/ [create]",
        )
        if created.status_code == 201:
            self.address_id = created.json()["public_id"]

    def clear_cart(self) -> None:
        self.client.post(
            "/api/v1/cart/clear/",
            json={"only_selected": False},
            headers=self.headers,
            name="/cart/clear/",
        )

    def fetch_e2e_product(self) -> dict | None:
        response = self.client.get(
            "/api/v1/products/?page_size=100", name="/products/?page_size=100"
        )
        if response.status_code != 200:
            return None
        items = response.json().get("results", [])
        product = next((item for item in items if "E2E" in item["name"]), None)
        if product is None:
            return None
        detail = self.client.get(
            f"/api/v1/products/{product['public_id']}/", name="/products/:id/"
        )
        return detail.json() if detail.status_code == 200 else None
