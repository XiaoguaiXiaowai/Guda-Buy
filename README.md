# GUDA 在线电商网站

GUDA 商城演示项目。技术栈：Django 5.2 + DRF + MariaDB + Redis + Celery；Vue 3 + Vite + TypeScript + Pinia + Element Plus。

当前进度：迭代 I0 工程基线。

## 目录结构

```text
backend/            Django 服务
  config/           settings（base/dev/prod/test）、urls、wsgi、celery
  apps/common/      统一异常、中间件、日志、分页、BaseModel、healthz
  scripts/          发布 / 回滚 / 备份 / 恢复脚本
frontend/           Vue 3 前端
deploy/             Nginx、Gunicorn、systemd、logrotate、生产环境变量模板
docs/               迭代计划、开发文档
```

## 本地开发（macOS）

### 1. 准备服务

```bash
brew services start mariadb
brew services start redis
mysql -u "$USER" -e "CREATE DATABASE IF NOT EXISTS guda_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

后端依赖 `mysqlclient`，本机需有 MariaDB 开发头文件；若未安装 `pkg-config`，同步依赖时显式指定路径：

```bash
export MYSQLCLIENT_CFLAGS="-I/opt/homebrew/opt/mariadb/include/mysql"
export MYSQLCLIENT_LDFLAGS="-L/opt/homebrew/opt/mariadb/lib -lmariadb"
```

### 2. 后端

```bash
cd backend
cp .env.example .env          # 按本机数据库账号修改 DB_USER/DB_PASSWORD/DB_HOST
uv sync
uv run python manage.py migrate
uv run python manage.py runserver 127.0.0.1:8000
```

本地使用 MariaDB `unix_socket` 认证时，把 `.env` 中 `DB_HOST` 设为 `localhost`。

### 3. 前端

```bash
cd frontend
pnpm install
pnpm dev                      # http://localhost:5173，/api 与 /healthz 已代理到 8000
```

## 质量闸（与 CI 一致）

```bash
# 后端
cd backend
uv run ruff check .
uv run ruff format --check .
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py spectacular --file /tmp/schema.yaml --validate
uv run coverage run -m pytest && uv run coverage report

# 前端
cd frontend
pnpm run lint
pnpm run type-check
pnpm run test
pnpm run build
```

## 端点

| 端点 | 说明 |
| --- | --- |
| `GET /healthz/` | 探活；DB/Redis 任一异常返回 503 + `COMMON_SERVICE_UNAVAILABLE` |
| `GET /api/schema/` | OpenAPI 3.0 契约 |
| `GET /api/docs/` | Swagger UI |
| `GET /api/v1/` | API 版本信息 |

统一错误响应结构：

```json
{
  "code": "COMMON_VALIDATION_ERROR",
  "message": "参数校验失败",
  "detail": {"fields": {"email": ["邮箱格式不正确"]}},
  "request_id": "req-8f1c2b9a",
  "timestamp": "2026-11-04T10:30:00+08:00"
}
```

所有响应携带 `X-Request-ID`；未传入时服务端生成，可据此检索 `logs/app.log` 与 `logs/error.log`。

## 生产部署（Ubuntu 24.04）

1. 创建用户与目录：

```bash
sudo useradd -r -s /bin/false guda
sudo mkdir -p /srv/guda/{app,env,run,logs,static,media,frontend,backups}
sudo chown -R guda:guda /srv/guda
```

2. 安装运行时：Python 3.12（uv）、Node 20 + pnpm 11、MariaDB、Redis、Nginx。

3. 首次部署：

```bash
sudo -u guda git clone <repo-url> /srv/guda/app
sudo cp /srv/guda/app/deploy/env.production.example /srv/guda/env/.env
sudo chmod 600 /srv/guda/env/.env && sudo chown guda:guda /srv/guda/env/.env
# 填写密钥、数据库、域名后：
sudo cp deploy/systemd/guda-*.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now guda-web guda-celery guda-celerybeat
sudo cp deploy/nginx/guda.conf /etc/nginx/sites-available/guda.conf && sudo ln -s /etc/nginx/sites-available/guda.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo cp deploy/logrotate/guda /etc/logrotate.d/guda
```

4. 后续发布与回滚：

```bash
cd /srv/guda/app && ./backend/scripts/publish.sh     # 拉取、迁移、构建、重启、探活
cd /srv/guda/app && ./backend/scripts/rollback.sh    # 回退到上一发布版本
```

5. 备份与恢复（保留 30 天）：

```bash
cd /srv/guda/app && ./backend/scripts/backup.sh
# 每天 03:00 定时备份：crontab -e (guda 用户)
# 0 3 * * * /srv/guda/app/backend/scripts/backup.sh >> /srv/guda/logs/backup.log 2>&1

# 恢复（FORCE=1 跳过交互确认）
cd /srv/guda/app && FORCE=1 ./backend/scripts/restore.sh db /srv/guda/backups/db-20261104-030000-<commit>.sql.gz
cd /srv/guda/app && FORCE=1 ./backend/scripts/restore.sh media /srv/guda/backups/media-20261104-030000-<commit>.tar.gz
```

数据库回滚使用备份恢复，不做自动逆向迁移；跨版本发布前先执行一次备份。

## 关键约定

- 金额一律使用字符串十进制，前端只做展示格式化，不做优惠计算。
- 密码、手机号、地址等敏感字段不得写入日志。
- 所有 API 错误必须复用 `apps/common/exceptions.py` 的统一结构。
- 业务模型继承 `apps/common/models.BaseModel`（`public_id`、`created_at`、`updated_at`、软删除）。
