# 备份恢复演练记录（T11.4 / V11-4）

## 环境

| 项 | 值 |
| --- | --- |
| 日期 | 2026-11-23 22:23 |
| 源库 | MariaDB 12.1.2 `guda_dev` |
| 备份脚本 | `backend/scripts/backup.sh` |
| 恢复脚本 | `backend/scripts/restore.sh`（`FORCE=1`，`ENV_FILE` 指向临时库配置） |
| 恢复目标 | 新建空库 `guda_restore_i11`（与源库隔离，不影响开发库） |
| 产物 | `/tmp/i11-drill/backups/db-20261123-222302-bc1f421.sql.gz`、`media-…tar.gz` |

## 步骤与耗时

| 步骤 | 命令 | 结果 | 耗时 |
| --- | --- | --- | --- |
| 1. 备份 | `ENV_FILE=backend/.env BACKUP_DIR=/tmp/i11-drill/backups bash backend/scripts/backup.sh` | db 30 KB + media 4.1 MB | 1s |
| 2. 完整性校验 | `gzip -t db-…sql.gz`、`gzip -t media-…tar.gz` | 均通过 | <1s |
| 3. 建空库 | `CREATE DATABASE guda_restore_i11` | 成功（utf8mb4） | <1s |
| 4. 异库恢复 | `FORCE=1 ENV_FILE=/tmp/i11-drill/restore.env bash backend/scripts/restore.sh db …` | 成功 | 2.9s |
| 5. 数据核对 | `SELECT COUNT(*), SUM(payable_amount), SUM(items_amount), SUM(discount_amount)` | 两侧一致 | <1s |
| 6. 服务指向恢复库启动 | `DB_NAME=guda_restore_i11 runserver 127.0.0.1:8003` | `/healthz/` 200（db/redis ok）、商品列表 200（count=5） | 约 4s |

## 核对结果

| 指标 | 源库 `guda_dev` | 恢复库 `guda_restore_i11` | 结论 |
| --- | --- | --- | --- |
| 订单条数 | 11 | 11 | 一致 |
| payable 金额汇总 | 2176.00 | 2176.00 | 一致 |
| items 金额汇总 | 2216.00 | 2216.00 | 一致 |
| discount 金额汇总 | 40.00 | 40.00 | 一致 |
| 表数量 | 35 | 35 | 一致 |

## 结论与遗留

- 备份完整性、恢复流程、数据核对、服务指向恢复库启动均通过，V11-4 达标。
- 启动验证使用独立端口 8003 与独立库 `guda_restore_i11`，验证后立即停止，未影响开发服务。
- 媒体文件恢复步骤已在脚本中覆盖，本次未展开核对（备份包 `gzip/tar` 校验通过）。
- 建议生产每月按本流程复演一次，并保留核对 SQL 输出。
