#!/usr/bin/env bash
# 一键发布：拉取代码 → 安装依赖 → 迁移 → 构建前端 → 重启服务 → 健康检查
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/guda/app}"
FRONTEND_DIR="/srv/guda/frontend"
BRANCH="${BRANCH:-main}"
SMOKE_URL="${SMOKE_URL:-https://guda.example.com/healthz/}"
PREV_FILE="/srv/guda/.last_release"

cd "$APP_DIR"

PREV_COMMIT="$(git rev-parse HEAD)"
echo "$PREV_COMMIT" > "$PREV_FILE"
echo "[publish] 记录回滚点：$PREV_COMMIT"

git fetch --prune origin
git reset --hard "origin/$BRANCH"
NEW_COMMIT="$(git rev-parse HEAD)"
echo "[publish] 目标版本：$NEW_COMMIT"

cd "$APP_DIR/backend"
uv sync --frozen
uv run python manage.py migrate --noinput
uv run python manage.py collectstatic --noinput

cd "$APP_DIR/frontend"
pnpm install --frozen-lockfile --prod=false
pnpm run build
sudo mkdir -p "$FRONTEND_DIR"
sudo rsync -a --delete "$APP_DIR/frontend/dist/" "$FRONTEND_DIR/"

sudo systemctl restart guda-web guda-celery guda-celerybeat

echo "[publish] 健康检查：$SMOKE_URL"
for i in $(seq 1 10); do
  if curl -fsS --max-time 5 "$SMOKE_URL"; then
    echo
    echo "[publish] 发布成功：$NEW_COMMIT"
    exit 0
  fi
  echo "[publish] 第 $i 次探活失败，3 秒后重试"
  sleep 3
done

echo "[publish] 健康检查失败，请执行 backend/scripts/rollback.sh"
exit 1
