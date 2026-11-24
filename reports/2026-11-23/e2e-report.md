# E2E 全链路测试报告（T11.1 / V11-1）

## 环境

| 项 | 值 |
| --- | --- |
| 日期 | 2026-11-23 |
| 代码版本 | `bc1f421`（工作区含 I11 改动） |
| 后端 | Django 5.2 + DRF，独立库 `guda_e2e`，Redis 前缀 `guda:e2e`，`127.0.0.1:8001`，`config.settings.e2e` |
| 前端 | Vue 3 + Vite，`127.0.0.1:5174`，`VITE_PROXY_TARGET=http://127.0.0.1:8001` |
| 浏览器 | Playwright 1.65.1 + 本机 Google Chrome（`channel: 'chrome'`） |
| 数据 | `seed_e2e` 幂等造数：`e2e_buyer/e2e_operator/e2e_support`、2 个 SKU、1 张满减券 |
| 执行 | `cd frontend && pnpm e2e`（`workers=1`、`retries=0`） |
| 留痕 | JUnit `frontend/reports/playwright.xml`，HTML `frontend/reports/playwright-html/`，失败自动 trace + 截图 |

## 结果

**8/8 通过，连续 3 次全绿（28.1s / 35.0s / 33.8s，后两次含冷启动），无重试、无 flaky。**

| # | 用例 | 覆盖场景 | 耗时 |
| --- | --- | --- | --- |
| 01 | `01-auth.spec.ts` | 注册（邮箱验证码）→ 登录 → 刷新保持登录 | 1.4s |
| 02 | `02-browse-cart.spec.ts` | 浏览分类 → 商品详情 → 选 SKU → 加购 | 1.5s |
| 03 | `03-checkout-coupon.spec.ts` | 改数量 → 勾选 → 结算 → 用券 → 提交订单 | 2.0s |
| 04 | `04-pay-success.spec.ts` | 模拟支付成功 → 订单待发货 → 站内消息 | 1.9s |
| 05 | `05-pay-fail-retry.spec.ts` | 支付失败 → 重新支付 → 成功 | 1.6s |
| 06 | `06-cancel-release.spec.ts` | 取消未支付订单 → 可用库存恢复 | 1.5s |
| 07 | `07-review-approve.spec.ts` | 确认收货 → 评价 → 后台审核 → 前台展示 | 4.5s |
| 08 | `08-support-flow.spec.ts` | 创建会话 → 客服接管 → 双向消息 → 关闭 | 11.8s |

## 用例设计要点

- 每个用例通过 API 自建所需数据（账号、地址、购物车、订单），不依赖执行顺序。
- 库存语义按 `可用库存 = stock - locked_stock` 断言，取消订单后 `locked_stock` 回落。
- 下单成功跳转 `/user/orders/{order_no}`，模拟支付入口为独立的 `/pay/{order_no}`。
- 后台确认框按钮文案为业务词（取消订单/确认收货/通过/接管/关闭会话），按文案定位。
- 验证码通过文件邮件后端 `backend/logs/e2e-mail` 读取，不依赖外部邮件服务。

## 发现并修复的缺陷

| 缺陷 | 现象 | 修复 |
| --- | --- | --- |
| 会话关闭状态不同步（前端） | 客服关闭会话后，用户端轮询只拉消息、不刷新会话状态，页面一直显示“进行中” | `SupportView.vue` 轮询内先刷新会话列表，检测到关闭后停止轮询并展示“会话已关闭”，输入框禁用 |

修复后用例 08 稳定通过，其余用例未回退。

## 结论

V11-1 通过：8 条链路全部通过，失败留痕与执行脚本齐备，可重复执行。
