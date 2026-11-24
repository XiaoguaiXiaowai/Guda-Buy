# 发布与回滚演练记录（T11.5 / V11-5）

## 环境与方式

| 项 | 值 |
| --- | --- |
| 日期 | 2026-11-23 22:29 |
| 代码版本 | `bc1f421`（工作区含 I11 改动） |
| 演练范围 | 迁移前备份 → 前端发布构建 → 发布后冒烟 → 回滚旧产物 → 回滚后冒烟 |
| 冒烟地址 | `http://127.0.0.1:8000`（本机 dev 后端） |
| 说明 | 本机未安装生产 Nginx/Systemd 单元，`publish.sh`/`rollback.sh` 中的 rsync 与 `systemctl restart` 未实际执行；构建、备份、冒烟、回滚产物切换均真实执行 |

## 发布演练

| 步骤 | 命令 | 结果 | 耗时 |
| --- | --- | --- | --- |
| 1. 迁移前备份 | `ENV_FILE=backend/.env BACKUP_DIR=/tmp/i11-drill/backups APP_DIR=$PWD MEDIA_DIR=$PWD/backend/media bash backend/scripts/backup.sh` | `db-20261124-022933-bc1f421.sql.gz` 生成 | 0.7s |
| 2. 记录回滚点 | `cp -R frontend/dist /tmp/i11-drill/release/dist-prev` | 69 个文件，`index.html` 哈希 `dc11cc31…` | <1s |
| 3. 数据库迁移 | `python manage.py migrate --noinput` | `No migrations to apply`（版本已同步） | 2.2s |
| 4. 前端构建 | `cd frontend && pnpm build` | 构建成功，`built in 4.66s`，69 个产物，`index.html` 哈希 `cac40809…` | 10.3s |
| 5. 发布后冒烟 | `SMOKE_MODE=public SMOKE_BASE_URL=http://127.0.0.1:8000 bash backend/scripts/smoke.sh` | 通过 6、失败 0（健康检查/商品列表/商品详情/CMS/错误信封/OpenAPI） | 2.2s |
| 6. 健康检查 | `GET /healthz/` | 200，`db=ok redis=ok` | <1s |

发布链路合计约 16s，远低于 15 分钟上限。

## 回滚演练

| 步骤 | 命令 | 结果 | 耗时 |
| --- | --- | --- | --- |
| 1. 恢复旧产物 | `rm -rf frontend/dist && cp -R /tmp/i11-drill/release/dist-prev frontend/dist` | 69 个文件，`index.html` 哈希回到 `dc11cc31…` | 0.1s |
| 2. 回滚后冒烟 | `SMOKE_MODE=public SMOKE_BASE_URL=http://127.0.0.1:8000 bash backend/scripts/smoke.sh` | 通过 6、失败 0 | 1.6s |
| 3. 健康检查 | `GET /healthz/` | 200 | <1s |

回滚链路合计约 2s，远低于 15 分钟上限；回滚前后产物哈希与快照完全一致。

## 发布检查单（生产执行）

发布前：

1. 确认 CI 门禁全绿（pytest / vitest / type-check / lint / build / E2E 8 条）。
2. 执行数据库备份并 `gzip -t` 校验。
3. 记录当前提交号，确认 `/srv/guda/.last_release` 可写。
4. 通知值班与业务方，确认发布窗口。

发布后：

1. `/healthz/` 返回 200 且 db/redis 均 ok。
2. `smoke.sh` 5 项通过。
3. 抽查首页、商品详情、加购、下单、支付回调。
4. `error.log` 无新增堆栈；5xx 比例无异常。

回滚触发条件：冒烟失败且 3 分钟内无法定位；5xx 比例持续 > 1%；核心链路不可用。
回滚后必须重新冒烟并确认 `/healthz/` 正常，数据库迁移按 `reverse` 方案评估。

## 结论

V11-5 通过：发布与回滚各完成一次，冒烟均通过，均在 15 分钟内完成；产物哈希验证回滚正确。
遗留：生产 Nginx/Systemd 重启与 rsync 环节待部署环境复核。
