#!/usr/bin/env bash
# 回滚到上一次发布前记录的提交
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/guda/app}"
SMOKE_URL="${SMOKE_URL:-https://guda.example.com/healthz/}"
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
uv sync --frozen
uv run python manage.py migrate --noinput
uv run python manage.py collectstatic --noinput

cd "$APP_DIR/frontend"
pnpm install --frozen-lockfile --prod=false
pnpm run build
sudo rsync -a --delete "$APP_DIR/frontend/dist/" /srv/guda/frontend/

sudo systemctl restart guda-web guda-celery guda-celerybeat

for i in $(seq 1 10); do
  if curl -fsS --max-time 5 "$SMOKE_URL"; then
    echo
    echo "[rollback] 回滚成功：$PREV_COMMIT"
    exit 0
  fi
  echo "[rollback] 第 $i 次探活失败，3 秒后重试"
  sleep 3
done

echo "[rollback] 回滚后健康检查仍失败，请立即人工介入" >&2
exit 1
