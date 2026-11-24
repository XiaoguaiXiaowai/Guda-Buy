# 测试报告归档 · 2026-11-23（I11 上线加固）

I11 验收时的全量质量快照，覆盖 I0～I11 全部能力；同日早前的 I8 快照已被本文件取代。

## 运行环境

| 项 | 值 |
| --- | --- |
| 归档时间 | 2026-11-23（执行跨至 2026-11-24 凌晨） |
| 代码版本 | `bc1f421`（工作区含 I11 改动） |
| 后端环境 | macOS · Python 3.12 · Django 5.2 · pytest 8.3.4 · coverage 7.6.9 |
| 前端环境 | Node 20 · Vitest 3.2.4 · Playwright 1.65.1（系统 Chrome） |
| 后端命令 | `.venv/bin/coverage run -m pytest` → `.venv/bin/coverage xml` |
| 前端命令 | `pnpm run type-check && pnpm run lint && pnpm run test:report` |
| E2E 命令 | `pnpm e2e`（独立库 `guda_e2e`，`workers=1`、`retries=0`） |

## 汇总

| 套件 | 用例 | 失败 | 覆盖率 | 报告文件 |
| --- | --- | --- | --- | --- |
| 后端 pytest（全量） | 417 | 0 | 97%（9322 行，315 未覆盖） | `backend-pytest.xml`、`backend-coverage.xml` |
| 前端 Vitest | 57 | 0 | — | `frontend-vitest.xml` |
| 前端 type-check / lint | — | 0 | — | 命令输出 |
| Playwright E2E | 8 | 0 | — | `e2e-playwright.xml`、`e2e-report.md`（连续 3 次全绿） |

## 后端分模块

| 模块 | 用例 |
| --- | --- |
| orders | 66 |
| coupons | 62 |
| cms | 49 |
| catalog | 43 |
| accounts | 37 |
| payments | 34 |
| reviews | 32 |
| cart | 27 |
| support | 25 |
| tests（I11 安全专项） | 15 |
| common | 14 |
| notifications | 13 |

## 性能基线（I11）

| 场景 | 并发 / 时长 | P95 | 错误率 | 报告 |
| --- | --- | --- | --- | --- |
| 读接口 | 50 / 5 分钟 | 10ms | 0.01% | `perf-report.md`、`perf-read_*.csv` |
| 下单 | 20 / 2 分钟 | 23ms（`/orders/`） | 0.011% | `perf-order_*.csv` |
| 支付回调 | 10 / 2 分钟 | 17ms（`/callback/`） | 0% | `perf-callback_*.csv` |

## 演练与安全

| 项 | 结论 | 报告 |
| --- | --- | --- |
| 安全测试 | 15 用例通过，高危/越权/泄漏均为 0 | `security-test.md` |
| 备份恢复 | 订单 11 条、金额 2176.00、35 张表一致；恢复库启动 healthz 200 | `backup-restore-drill.md` |
| 发布/回滚 | 发布约 14s、回滚约 2s，冒烟各 6/6 | `release-rollback-drill.md` |
| 监控告警 | 探活成功/失败退出码验证；告警规则 3 组 9 条 | `docs/运维手册.md` |

## 归档规范

| 产物 | 位置 | 是否入库 |
| --- | --- | --- |
| 本次 pytest JUnit | `backend/reports/pytest.xml` | 否 |
| 本次覆盖率 XML | `backend/reports/coverage.xml` | 否 |
| 本次 Vitest JUnit | `frontend/reports/vitest.xml` | 否 |
| Playwright JUnit / HTML | `frontend/reports/playwright.xml`、`playwright-html/` | 否 |
| 迭代归档快照 | `reports/<日期>/` | 是 |
