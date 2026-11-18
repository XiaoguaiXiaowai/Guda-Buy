# 测试报告归档 · 2026-11-18

I0～I6 完成后首份结构化测试报告基线。此前各迭代仅有终端输出与交接文档中的文字数字，无落盘报告，本归档用于补齐可追溯证据。

## 运行环境

| 项 | 值 |
| --- | --- |
| 归档时间 | 2026-11-18 17:08 (GMT+8) |
| 代码版本 | `main` @ `5bab840`（工作区含本次质量改造改动） |
| 后端环境 | macOS · Python 3.12 · Django 5.2.7 · pytest 8.3.4 · coverage 7.6.9 |
| 前端环境 | Node 20 · Vitest 3.2.4 |
| 后端命令 | `uv run coverage run -m pytest` → `coverage xml` / `coverage html` |
| 前端命令 | `pnpm run test:report` |

## 汇总

| 套件 | 用例 | 失败 | 覆盖率 | 报告文件 |
| --- | --- | --- | --- | --- |
| 后端 pytest（全量） | 267 | 0 | 97.0%（6025/6211 行） | `backend-pytest.xml`、`backend-coverage.xml` |
| 前端 Vitest | 33 | 0 | — | `frontend-vitest.xml` |

后端 HTML 覆盖率明细：`backend/htmlcov/index.html`（本地生成，未入库）。

## 后端分模块

| 模块 | 承接迭代 | 用例 | 覆盖率 |
| --- | --- | --- | --- |
| common | I0 工程基线 | 14 | 90.9% |
| accounts | I1 会员账号 | 37 | 96.8% |
| catalog | I2 商品中心 | 43 | 95.9% |
| cms | I3 内容运营 | 49 | 92.3% |
| cart | I4 购物车 | 27 | 99.2% |
| orders | I5 订单系统 | 63 | 97.1% |
| payments | I6 支付流程 | 34 | 97.4% |

订单与购物车均含 `TransactionTestCase` 并发用例（`test_order_concurrency.py`、`test_cart_concurrency.py`）。

## 前端分模块

| 用例文件 | 承接迭代 | 用例 |
| --- | --- | --- |
| `format.spec.ts` | I0 工具函数 | 4 |
| `auth.spec.ts` | I1 登录校验 | 5 |
| `catalog.spec.ts` | I2 商品展示 | 9 |
| `cms.spec.ts` | I3 内容位 | 10 |
| `cart.spec.ts` | I4 购物车 | 5 |

I5（结算/订单页）、I6（收银台/支付结果页）暂无前端用例，为已知缺口。

## 冒烟测试

`backend/scripts/smoke.sh`，2026-11-18 对本地 `http://127.0.0.1:8000` 实测：

- public 模式：5 项阶段 / 6 条断言全通过（健康检查、商品列表与详情、CMS 首页内容位、未登录 401 错误信封、OpenAPI schema）。
- full 模式：5 项阶段 / 11 条断言全通过（登录 → 加购 → 建地址 → 下单 → 发起模拟支付 → 回调签名校验 → 订单 PAID 闭环）。

发布与回滚脚本（`publish.sh` / `rollback.sh`）已改为调用该脚本，失败重试 3 次后判发布失败。

## 归档规范

| 产物 | 位置 | 是否入库 |
| --- | --- | --- |
| 每次运行的 pytest JUnit | `backend/reports/pytest.xml` | 否（`.gitignore`） |
| 每次运行的覆盖率 XML | `backend/reports/coverage.xml` | 否 |
| 每次运行的 Vitest JUnit | `frontend/reports/vitest.xml` | 否 |
| 迭代归档快照 | `reports/<日期>/` | 是 |
| CI 产物 | GitHub Actions artifact（保留 30 天） | — |

后续每次迭代关闭时，将当次 `backend/reports/*`、`frontend/reports/*` 复制到 `reports/<迭代>/` 一并提交，作为该迭代的质量证据。
