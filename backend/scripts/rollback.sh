#!/usr/bin/env bash
# 回滚到上一次发布前记录的提交
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/guda/app}"
SMOKE_URL="${SMOKE_URL:-https://guda.example.com/healthz/}"
SMOKE_BASE_URL="${SMOKE_BASE_URL:-${SMOKE_URL%%/healthz*}}"
PREV_FILE="/srv/guda/.last_release"

if [[ ! -f "$PREV_FILE" ]]; then
  echo "[rollback] 未找到回滚点 $PREV_FILE，终止" >&2
  exit 1
fi

PREV_COMMIT="$(cat "$PREV_FILE")"
cd "$APP_DIR"
CURRENT_COMMIT="$(git rev-parse HEAD)"
echo "[rollback] 当前 $CURRENT_COMMIT → 回滚到 $PREV_COMMIT"

git reset --hard "$PREV_COMMIT"
echo "$CURRENT_COMMIT" > "$PREV_FILE"

cd "$APP_DIR/backend"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.prod}"
uv sync --frozen
uv run python manage.py migrate --noinput
uv run python manage.py collectstatic --noinput

cd "$APP_DIR/frontend"
pnpm install --frozen-lockfile --prod=false
pnpm run build
sudo rsync -a --delete "$APP_DIR/frontend/dist/" /srv/guda/frontend/

sudo systemctl restart guda-web guda-celery guda-celerybeat

echo "[rollback] 冒烟验证：$SMOKE_BASE_URL（5 项，含健康检查）"
SMOKE_OK=0
for i in $(seq 1 3); do
  if SMOKE_BASE_URL="$SMOKE_BASE_URL" bash "$APP_DIR/backend/scripts/smoke.sh"; then
    SMOKE_OK=1
    break
  fi
  echo "[rollback] 第 $i 次冒烟失败，5 秒后重试"
  sleep 5
done

if [ "$SMOKE_OK" = "1" ]; then
  echo "[rollback] 回滚成功：$PREV_COMMIT"
  exit 0
fi

echo "[rollback] 回滚后冒烟仍失败，请立即人工介入" >&2
exit 1
