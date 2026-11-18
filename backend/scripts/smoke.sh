#!/usr/bin/env bash
# 冒烟测试（迭代计划 T11.5）：发布/回滚后验证 5 项核心链路，也可本地对 dev 环境执行。
#
# 用法：
#   SMOKE_BASE_URL=https://192.168.121.126 ./backend/scripts/smoke.sh
#   SMOKE_BASE_URL=http://127.0.0.1:8000 \
#     SMOKE_ACCOUNT=demo@example.com SMOKE_PASSWORD=Demo12345 \
#     ./backend/scripts/smoke.sh
#
# 环境变量：
#   SMOKE_BASE_URL      站点根地址；缺省时由 SMOKE_URL 去掉 /healthz/ 推导，再缺省为 https://guda.example.com
#   SMOKE_ACCOUNT       冒烟账号（邮箱或用户名）
#   SMOKE_PASSWORD      冒烟账号密码
#   SMOKE_MODE          auto | public | full，默认 auto（配齐账号密码即 full）
#   SMOKE_REQUIRE_AUTH  1 = 缺少凭据时直接判失败（预发/生产流水线建议开启）
#   SMOKE_TIMEOUT       单请求超时秒数，默认 10
#
# public 模式 5 项：健康检查 / 商品目录 / CMS 内容位 / 错误信封 / OpenAPI 契约
# full   模式 5 项：健康检查 / 商品目录 / CMS 内容位 / 登录+加购 / 下单+模拟支付回调
#
# 注意：full 模式会真实创建 1 笔演示订单并完成模拟支付（占库存、累加销量），
#       仅建议在预发或本地执行；对生产请用 public 模式。
#
# 退出码：0 通过（含按策略跳过）；1 存在失败项或网络不可达。
set -uo pipefail

TIMEOUT="${SMOKE_TIMEOUT:-10}"
BASE="${SMOKE_BASE_URL:-}"
if [ -z "$BASE" ] && [ -n "${SMOKE_URL:-}" ]; then
  BASE="${SMOKE_URL%%/healthz*}"
fi
BASE="${BASE:-https://guda.example.com}"
BASE="${BASE%/}"

MODE="${SMOKE_MODE:-auto}"
if [ "$MODE" = "auto" ]; then
  if [ -n "${SMOKE_ACCOUNT:-}" ] && [ -n "${SMOKE_PASSWORD:-}" ]; then
    MODE="full"
  else
    MODE="public"
  fi
fi

REQUIRE_AUTH="${SMOKE_REQUIRE_AUTH:-0}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [ -t 1 ]; then
  G=$'\033[32m' R=$'\033[31m' Y=$'\033[33m' N=$'\033[0m'
else
  G="" R="" Y="" N=""
fi

PASS=0
FAIL=0
SKIP=0
AUTH=()

ok() { PASS=$((PASS + 1)); printf "  ${G}✓${N} %s\n" "$1"; }
bad() { FAIL=$((FAIL + 1)); printf "  ${R}✗${N} %s\n" "$1"; }
skipped() { SKIP=$((SKIP + 1)); printf "  ${Y}–${N} %s（跳过）\n" "$1"; }
step() { printf "\n[%s] %s\n" "$1" "$2"; }

# jget <json文件> <a.b.0.c>：安全取字段，取不到返回空串
jget() {
  python3 - "$1" "$2" <<'PY'
import json, sys
try:
    data = json.load(open(sys.argv[1]))
except Exception:
    print("")
    raise SystemExit(0)
for part in sys.argv[2].split("."):
    try:
        data = data[int(part)] if part.isdigit() else data[part]
    except Exception:
        print("")
        raise SystemExit(0)
print("" if data is None else data)
PY
}

# detail：失败时优先回显响应体，无响应体时回显 curl 错误
detail() {
  if [ -s "$TMP/body" ]; then
    head -c 200 "$TMP/body"
  else
    head -c 200 "$TMP/err"
  fi
}

# request <METHOD> <PATH> [JSON_BODY] [额外 curl 参数...]
# 结束后 CODE=HTTP 状态码，响应体在 $TMP/body
request() {
  local method="$1" path="$2"
  shift 2
  local body=""
  if [ $# -gt 0 ] && [ "${1:0:1}" != "-" ]; then
    body="$1"
    shift
  fi
  local args=(-sS --max-time "$TIMEOUT" -o "$TMP/body" -w "%{http_code}" -X "$method")
  if [ -n "$body" ]; then
    args+=(-H "Content-Type: application/json" -d "$body")
  fi
  if [ ${#AUTH[@]} -gt 0 ]; then
    args+=("${AUTH[@]}")
  fi
  args+=("$@" "$BASE$path")
  : > "$TMP/body"
  CODE="$(curl "${args[@]}" 2>"$TMP/err" || true)"
  CODE="${CODE:-000}"
}

printf "冒烟目标：%s\n模式：%s\n" "$BASE" "$MODE"

# ---------------------------------------------------------------------------
step "1/5" "健康检查 GET /healthz/"
request GET /healthz/
if [ "$CODE" = "200" ] && [ "$(jget "$TMP/body" db)" = "ok" ] && [ "$(jget "$TMP/body" redis)" = "ok" ]; then
  ok "healthz 200，db/redis 均 ok"
else
  bad "healthz 期望 200 且 db/redis=ok，实际 ${CODE}：$(detail)"
fi

# ---------------------------------------------------------------------------
step "2/5" "商品目录 GET /api/v1/products/ 与详情"
PRODUCT_ID=""
SKU_ID=""
request GET "/api/v1/products/?page_size=1"
LIST_COUNT="$(jget "$TMP/body" count)"
PRODUCT_ID="$(jget "$TMP/body" results.0.public_id)"
if [ "$CODE" = "200" ] && [ -n "$PRODUCT_ID" ]; then
  ok "商品列表 200，在售 $LIST_COUNT 件，首件 $PRODUCT_ID"
  request GET "/api/v1/products/$PRODUCT_ID/"
  SKU_ID="$(jget "$TMP/body" skus.0.public_id)"
  SKU_STOCK="$(jget "$TMP/body" skus.0.stock)"
  if [ "$CODE" = "200" ] && [ -n "$SKU_ID" ]; then
    ok "商品详情 200，SKU ${SKU_ID}（库存 ${SKU_STOCK}）"
  else
    bad "商品详情期望 200 且含 SKU，实际 $CODE"
  fi
else
  bad "商品列表期望 200 且非空，实际 ${CODE}（count=${LIST_COUNT}）"
fi

# ---------------------------------------------------------------------------
step "3/5" "CMS 内容位 GET /api/v1/cms/home/"
request GET /api/v1/cms/home/
if [ "$CODE" = "200" ]; then
  ok "首页内容位 200"
else
  bad "首页内容位期望 200，实际 ${CODE}：$(detail)"
fi

# ---------------------------------------------------------------------------
if [ "$MODE" = "full" ]; then
  step "4/5" "登录并加购"
  request POST /api/v1/auth/login/ "{\"account\":\"${SMOKE_ACCOUNT}\",\"password\":\"${SMOKE_PASSWORD}\"}"
  ACCESS="$(jget "$TMP/body" access)"
  if [ "$CODE" = "200" ] && [ -n "$ACCESS" ]; then
    AUTH=(-H "Authorization: Bearer $ACCESS")
    ok "登录 200，已取得 access"
  else
    bad "登录期望 200 且返回 access，实际 ${CODE}：$(detail)"
  fi

  CART_ITEM=""
  if [ -n "${AUTH[0]:-}" ] && [ -n "$SKU_ID" ]; then
    request POST /api/v1/cart/items/ "{\"sku_public_id\":\"$SKU_ID\",\"quantity\":1}"
    if [ "$CODE" = "201" ] || [ "$CODE" = "200" ]; then
      CART_ITEM="$(jget "$TMP/body" public_id)"
      ok "加购成功，购物车项 $CART_ITEM"
    else
      bad "加购期望 201，实际 ${CODE}：$(detail)"
    fi
  fi

  step "5/5" "下单并完成模拟支付"
  ADDR=""
  ORDER_NO=""
  if [ -n "$CART_ITEM" ]; then
    request GET /api/v1/users/me/addresses/
    ADDR="$(jget "$TMP/body" 0.public_id)"
    if [ -z "$ADDR" ]; then
      request POST /api/v1/users/me/addresses/ \
        '{"receiver_name":"冒烟测试","phone":"13800138000","province":"广东省","city":"深圳市","district":"南山区","detail":"冒烟地址 1 号","postal_code":"518000"}'
      ADDR="$(jget "$TMP/body" public_id)"
      if [ "$CODE" = "201" ] && [ -n "$ADDR" ]; then
        ok "创建冒烟地址 $ADDR"
      else
        bad "创建冒烟地址失败，实际 ${CODE}：$(detail)"
      fi
    else
      ok "复用已有地址 $ADDR"
    fi

    if [ -n "$ADDR" ]; then
      request POST /api/v1/orders/ \
        "{\"cart_item_public_ids\":[\"$CART_ITEM\"],\"address_public_id\":\"$ADDR\"}" \
        -H "Idempotency-Key: smoke-$(date +%s)-$$"
      ORDER_NO="$(jget "$TMP/body" order_no)"
      if [ "$CODE" = "201" ] || [ "$CODE" = "200" ]; then
        ok "下单成功，订单号 $ORDER_NO"
      else
        bad "下单期望 201，实际 ${CODE}：$(detail)"
      fi
    fi
  else
    skipped "未取得购物车项，跳过下单与支付"
  fi

  if [ -n "$ORDER_NO" ]; then
    request POST "/api/v1/payments/$ORDER_NO/mock-pay/" '{"channel":"ALIPAY_MOCK"}'
    PAY_NO="$(jget "$TMP/body" payment_no)"
    PAY_AMOUNT="$(jget "$TMP/body" amount)"
    PAY_SIGN="$(jget "$TMP/body" sign)"
    if [ "$CODE" = "200" ] && [ -n "$PAY_NO" ] && [ -n "$PAY_SIGN" ]; then
      ok "发起模拟支付 ${PAY_NO}，金额 $PAY_AMOUNT"
      request POST /api/v1/payments/callback/ \
        "{\"payment_no\":\"$PAY_NO\",\"amount\":\"$PAY_AMOUNT\",\"status\":\"SUCCESS\",\"signature\":\"$PAY_SIGN\",\"transaction_ref\":\"smoke\"}"
      if [ "$CODE" = "200" ]; then
        ok "回调 200，签名校验通过"
      else
        bad "回调期望 200，实际 ${CODE}：$(detail)"
      fi
      request GET "/api/v1/orders/$ORDER_NO/"
      ORDER_STATUS="$(jget "$TMP/body" status)"
      if [ "$ORDER_STATUS" = "PAID" ]; then
        ok "订单状态 PAID，支付链路闭环"
      else
        bad "订单期望 PAID，实际 $ORDER_STATUS"
      fi
    else
      bad "发起模拟支付期望 200 且含 sign，实际 ${CODE}：$(detail)"
    fi
  fi
else
  step "4/5" "鉴权与错误信封 GET /api/v1/cart/（未登录）"
  AUTH=()
  request GET /api/v1/cart/
  ERR_CODE="$(jget "$TMP/body" code)"
  ERR_MSG="$(jget "$TMP/body" message)"
  ERR_RID="$(jget "$TMP/body" request_id)"
  ERR_TS="$(jget "$TMP/body" timestamp)"
  if [ "$CODE" = "401" ] && [ -n "$ERR_CODE" ] && [ -n "$ERR_MSG" ] && [ -n "$ERR_RID" ] && [ -n "$ERR_TS" ]; then
    ok "未登录 401，错误信封含 code/message/request_id/timestamp"
  else
    bad "错误信封期望 401 且字段齐全，实际 ${CODE}：$(detail)"
  fi

  step "5/5" "OpenAPI 契约 GET /api/schema/"
  request GET /api/schema/
  if [ "$CODE" = "200" ] && grep -q "openapi" "$TMP/body" 2>/dev/null; then
    ok "schema 200，契约可生成"
  elif [ "$CODE" = "403" ] || [ "$CODE" = "302" ]; then
    skipped "schema 被网关限制（${CODE}），视为通过"
  else
    bad "schema 期望 200，实际 $CODE"
  fi

  if [ "$REQUIRE_AUTH" = "1" ]; then
    bad "SMOKE_REQUIRE_AUTH=1 但未提供 SMOKE_ACCOUNT/SMOKE_PASSWORD"
  fi
fi

# ---------------------------------------------------------------------------
printf "\n冒烟结果：通过 %d，失败 %d，跳过 %d\n" "$PASS" "$FAIL" "$SKIP"
if [ "$FAIL" -gt 0 ]; then
  printf "%s冒烟失败，禁止放行；生产请立即执行 rollback.sh%s\n" "$R" "$N" >&2
  exit 1
fi
printf "%s冒烟通过%s\n" "$G" "$N"
exit 0
