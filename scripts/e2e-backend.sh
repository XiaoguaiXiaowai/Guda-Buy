#!/usr/bin/env bash
# I11 E2E 独立后端：创建/迁移 guda_e2e 测试库，灌入固定数据后启动 8001。
# 由 Playwright webServer 调用，也可手工执行：bash scripts/e2e-backend.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ENV_FILE="${ENV_FILE:-$ROOT_DIR/backend/.env}"
E2E_DB="${E2E_DB:-guda_e2e}"
BACKEND_PORT="${E2E_BACKEND_PORT:-8001}"

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

PY="$ROOT_DIR/backend/.venv/bin/python"
export DB_NAME="$E2E_DB"
export REDIS_KEY_PREFIX="guda:e2e"
export DJANGO_SETTINGS_MODULE="config.settings.e2e"
# 刷新 Cookie 的 Origin 白名单需与 E2E 前端地址一致
export APP_SITE_URL="http://127.0.0.1:${E2E_FRONTEND_PORT:-5174}"
export GUDA_DISABLE_THROTTLE=1

if [[ "${DB_HOST:-127.0.0.1}" == "localhost" ]]; then
  CONN_ARGS=()
else
  CONN_ARGS=(-h "${DB_HOST:-127.0.0.1}" -P "${DB_PORT:-3306}")
fi

echo "[e2e] 准备独立测试库 $DB_NAME"
mysql "${CONN_ARGS[@]+"${CONN_ARGS[@]}"}" -u "$DB_USER" \
  ${DB_PASSWORD:+-p"$DB_PASSWORD"} \
  -e "CREATE DATABASE IF NOT EXISTS \`$DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

cd "$ROOT_DIR/backend"
"$PY" manage.py migrate --noinput
"$PY" manage.py init_roles
"$PY" manage.py seed_e2e

echo "[e2e] 启动后端 http://127.0.0.1:$BACKEND_PORT"
exec "$PY" manage.py runserver "127.0.0.1:$BACKEND_PORT" --noreload
