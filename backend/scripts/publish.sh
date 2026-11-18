#!/usr/bin/env bash
# 一键发布：拉取代码 → 安装依赖 → 迁移 → 构建前端 → 重启服务 → 健康检查
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/guda/app}"
FRONTEND_DIR="/srv/guda/frontend"
BRANCH="${BRANCH:-main}"
SMOKE_URL="${SMOKE_URL:-https://guda.example.com/healthz/}"
SMOKE_BASE_URL="${SMOKE_BASE_URL:-${SMOKE_URL%%/healthz*}}"
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
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.prod}"
uv sync --frozen
uv run python manage.py migrate --noinput
uv run python manage.py collectstatic --noinput

cd "$APP_DIR/frontend"
pnpm install --frozen-lockfile --prod=false
pnpm run build
sudo mkdir -p "$FRONTEND_DIR"
sudo rsync -a --delete "$APP_DIR/frontend/dist/" "$FRONTEND_DIR/"

sudo systemctl restart guda-web guda-celery guda-celerybeat

echo "[publish] 冒烟验证：$SMOKE_BASE_URL（5 项，含健康检查）"
SMOKE_OK=0
for i in $(seq 1 3); do
  if SMOKE_BASE_URL="$SMOKE_BASE_URL" bash "$APP_DIR/backend/scripts/smoke.sh"; then
    SMOKE_OK=1
    break
  fi
  echo "[publish] 第 $i 次冒烟失败，5 秒后重试"
  sleep 5
done

if [ "$SMOKE_OK" = "1" ]; then
  echo "[publish] 发布成功：$NEW_COMMIT"
  exit 0
fi

echo "[publish] 冒烟未通过，请执行 backend/scripts/rollback.sh"
exit 1
