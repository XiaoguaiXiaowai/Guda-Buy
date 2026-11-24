#!/usr/bin/env bash
# I11 性能压测：gunicorn(4 workers) + Locust 三组场景，CSV 输出到 reports/<日期>/
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/reports/$(date +%F)}"
PERF_HOST="${PERF_HOST:-http://127.0.0.1:8002}"
READ_DURATION="${READ_DURATION:-5m}"
ORDER_DURATION="${ORDER_DURATION:-2m}"
CALLBACK_DURATION="${CALLBACK_DURATION:-2m}"

export ENV_FILE="${ENV_FILE:-$ROOT_DIR/backend/.env}"
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

export DB_NAME="${E2E_DB:-guda_e2e}"
export REDIS_KEY_PREFIX="guda:e2e"
export DJANGO_SETTINGS_MODULE="config.settings.e2e"
export APP_SITE_URL="http://127.0.0.1:5174"
export GUDA_DISABLE_THROTTLE=1

mkdir -p "$OUT_DIR"
cd "$ROOT_DIR/backend"
VENV="$ROOT_DIR/backend/.venv"

"$VENV/bin/python" manage.py migrate --noinput >/dev/null
"$VENV/bin/python" manage.py seed_e2e >/dev/null

cleanup() {
  if [[ -f /tmp/guda-perf.pid ]]; then
    kill "$(cat /tmp/guda-perf.pid)" 2>/dev/null || true
    rm -f /tmp/guda-perf.pid
  fi
}
trap cleanup EXIT
cleanup

"$VENV/bin/gunicorn" config.wsgi:application \
  --bind 127.0.0.1:8002 --workers 4 --threads 2 --timeout 120 \
  --pid /tmp/guda-perf.pid --daemon \
  --access-logfile "$OUT_DIR/perf-access.log" \
  --error-logfile "$OUT_DIR/perf-error.log"

for _ in $(seq 1 30); do
  if "$VENV/bin/python" -c "import urllib.request;urllib.request.urlopen('$PERF_HOST/healthz/', timeout=2)" 2>/dev/null; then
    break
  fi
  sleep 1
done

cd "$ROOT_DIR/backend/perf"

"$VENV/bin/locust" -f locust_read.py --headless -u 50 -r 10 -t "$READ_DURATION" \
  --host "$PERF_HOST" --csv "$OUT_DIR/perf-read" --only-summary --loglevel WARNING

"$VENV/bin/locust" -f locust_order.py --headless -u 20 -r 5 -t "$ORDER_DURATION" \
  --host "$PERF_HOST" --csv "$OUT_DIR/perf-order" --only-summary --loglevel WARNING

"$VENV/bin/locust" -f locust_callback.py --headless -u 10 -r 2 -t "$CALLBACK_DURATION" \
  --host "$PERF_HOST" --csv "$OUT_DIR/perf-callback" --only-summary --loglevel WARNING

echo "压测完成，报告目录：$OUT_DIR"
