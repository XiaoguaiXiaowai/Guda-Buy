#!/usr/bin/env bash
# 外部探活脚本（迭代计划 T11.6）：校验 /healthz/ 的 HTTP 状态与 db/redis 字段。
#
# 用法：
#   PROBE_URL=https://guda.example.com/healthz/ ./deploy/scripts/health-probe.sh
#   PROBE_URL=http://127.0.0.1:8000/healthz/ ./deploy/scripts/health-probe.sh
#
# 环境变量：
#   PROBE_URL       探活地址，默认 https://guda.example.com/healthz/
#   PROBE_TIMEOUT   单次请求超时秒数，默认 5
#   PROBE_RETRIES   失败重试次数（不含首次），默认 2
#   PROBE_INTERVAL  重试间隔秒数，默认 3
#
# 退出码：0 健康；1 HTTP 非 200、db/redis 非 ok 或网络不可达。
# 建议接入：systemd timer（30 秒一次）、Prometheus blackbox_exporter、云拨测。
set -uo pipefail

URL="${PROBE_URL:-https://guda.example.com/healthz/}"
TIMEOUT="${PROBE_TIMEOUT:-5}"
RETRIES="${PROBE_RETRIES:-2}"
INTERVAL="${PROBE_INTERVAL:-3}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# jfield <json文件> <字段名>：安全取字段，取不到返回空串
jfield() {
  python3 - "$1" "$2" <<'PY'
import json, sys
try:
    data = json.load(open(sys.argv[1]))
except Exception:
    print("")
    raise SystemExit(0)
value = data
for part in sys.argv[2].split("."):
    if not isinstance(value, dict):
        value = ""
        break
    value = value.get(part, "")
print("" if value is None else value)
PY
}

attempt() {
  local code rid db redis status
  code="$(curl -sS --max-time "$TIMEOUT" -o "$TMP/body" -w '%{http_code}' \
    -H 'Cache-Control: no-cache' "$URL" 2>"$TMP/err" || true)"
  code="${code:-000}"
  if [ "$code" != "200" ]; then
    rid="$(jfield "$TMP/body" request_id)"
    printf '[probe] FAIL http=%s request_id=%s url=%s detail=%s%s\n' \
      "$code" "${rid:--}" "$URL" \
      "$(head -c 160 "$TMP/body" 2>/dev/null)" "$(head -c 120 "$TMP/err" 2>/dev/null)"
    return 1
  fi
  db="$(jfield "$TMP/body" db)"
  redis="$(jfield "$TMP/body" redis)"
  status="$(jfield "$TMP/body" status)"
  if [ "$db" = "ok" ] && [ "$redis" = "ok" ]; then
    printf '[probe] OK http=200 status=%s db=ok redis=ok url=%s\n' "${status:-ok}" "$URL"
    return 0
  fi
  printf '[probe] FAIL http=200 status=%s db=%s redis=%s url=%s\n' \
    "${status:--}" "${db:--}" "${redis:--}" "$URL"
  return 1
}

i=0
while :; do
  if attempt; then
    exit 0
  fi
  if [ "$i" -ge "$RETRIES" ]; then
    break
  fi
  i=$((i + 1))
  sleep "$INTERVAL"
done

printf '[probe] 连续 %d 次探测失败，请检查服务与依赖\n' "$((RETRIES + 1))" >&2
exit 1
