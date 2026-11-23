# 测试报告归档 · 2026-11-23

I8（通知与用户中心）验收时的全量质量快照，覆盖 I0～I8 既有能力。

## 运行环境

| 项 | 值 |
| --- | --- |
| 归档时间 | 2026-11-23 17:07 (GMT+8) |
| 代码版本 | `main` @ `90a87c9`（工作区含 I8 改动） |
| 后端环境 | macOS · Python 3.12 · Django 5.2 · pytest · coverage |
| 前端环境 | Node 20 · Vitest 3.2.4 |
| 后端命令 | `uv run coverage run -m pytest` → `coverage xml` |
| 前端命令 | `pnpm run test:report` |

## 汇总

| 套件 | 用例 | 失败 | 覆盖率 | 报告文件 |
| --- | --- | --- | --- | --- |
| 后端 pytest（全量） | 374 | 0 | 97%（7811 行，244 未覆盖） | `backend-pytest.xml`、`backend-coverage.xml` |
| 前端 Vitest | 54 | 0 | — | `frontend-vitest.xml` |

## 后端分模块

| 模块 | 承接迭代 | 用例 |
| --- | --- | --- |
| orders | I5 订单 / I8 交易汇总 | 66 |
| coupons | I7 优惠券 / I8 到期提醒 | 62 |
| cms | I3 内容运营 | 49 |
| catalog | I2 商品中心 | 43 |
| accounts | I1 会员账号 | 37 |
| payments | I6 支付 / I8 支付消息 | 34 |
| reviews | I9 用户评价（并行开发中） | 29 |
| cart | I4 购物车 | 27 |
| common | I0 工程基线 | 14 |
| notifications | I8 站内消息 | 13 |

通知模块覆盖：`models.py` 97%、`services.py` 92%、`selectors.py` 100%、`api.py` 100%。

## 前端分模块

| 用例文件 | 承接迭代 | 用例 |
| --- | --- | --- |
| `format.spec.ts` | I0 工具函数 | 4 |
| `auth.spec.ts` | I1 登录校验 | 5 |
| `catalog.spec.ts` | I2 商品展示 | 9 |
| `cms.spec.ts` | I3 内容位 | 10 |
| `cart.spec.ts` | I4 购物车 | 5 |
| `coupon.spec.ts` | I7 优惠券 | 6 |
| `review.spec.ts` | I9 用户评价（并行开发中） | 4 |
| `notification.spec.ts` | I8 消息类型与未读轮询 | 11 |

## I8 验收口径

- 支付成功、发货、取消（含超时取消）、券到期四类事件均通过 `on_commit` 落消息，主事务不受通知失败影响。
- 未读数 SQL 计数；单条已读幂等，越权返回 404 `NOTIFY_NOT_FOUND`；全部已读返回更新条数。
- 交易记录汇总按状态分组计数与金额，`paid_amount` 仅统计已支付/已发货/已完成，金额为两位小数字符串。

## 归档规范

| 产物 | 位置 | 是否入库 |
| --- | --- | --- |
| 每次运行的 pytest JUnit | `backend/reports/pytest.xml` | 否 |
| 每次运行的覆盖率 XML | `backend/reports/coverage.xml` | 否 |
| 每次运行的 Vitest JUnit | `frontend/reports/vitest.xml` | 否 |
| 迭代归档快照 | `reports/<日期>/` | 是 |
