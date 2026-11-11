#!/usr/bin/env bash
# macOS 本地开发一键启动：Django(8000) + Vite(5173)
# 用法：./scripts/dev-start.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.dev"
BACKEND_PORT=8000
FRONTEND_PORT=5173
mkdir -p "$RUN_DIR"

log() { echo "[dev] $*"; }

is_alive() { kill -0 "$1" 2>/dev/null; }

port_busy() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

start_one() {
  local name="$1" port="$2" pid_file="$RUN_DIR/$1.pid"
  shift 2

  if [[ -f "$pid_file" ]]; then
    local old_pid
    old_pid="$(cat "$pid_file")"
    if is_alive "$old_pid"; then
      log "$name 已在运行（PID ${old_pid}），跳过"
      return 0
    fi
    rm -f "$pid_file"
  fi

  if port_busy "$port"; then
    log "端口 $port 已被其他进程占用，请先执行：lsof -nP -iTCP:$port -sTCP:LISTEN"
    return 1
  fi

  nohup "$@" > "$RUN_DIR/$name.log" 2>&1 &
  echo $! > "$pid_file"
  log "$name 已启动（PID $(cat "$pid_file")），日志：.dev/$name.log"
}

# ---- 前置检查 ----
[[ -f "$ROOT_DIR/backend/.env" ]] || {
  log "缺少 backend/.env，请先复制 backend/.env.example 并按本机修改"
  exit 1
}
[[ -x "$ROOT_DIR/backend/.venv/bin/python" ]] || {
  log "缺少后端虚拟环境，请先执行：cd backend && uv sync"
  exit 1
}
[[ -x "$ROOT_DIR/frontend/node_modules/.bin/vite" ]] || {
  log "缺少前端依赖，请先执行：cd frontend && pnpm install"
  exit 1
}

command -v redis-cli >/dev/null 2>&1 && redis-cli ping >/dev/null 2>&1 || {
  log "警告：Redis 未响应，/healthz/ 将返回 503（brew services start redis）"
}

# ---- 启动后端（--noreload 保证 PID 即服务进程） ----
cd "$ROOT_DIR/backend"
start_one backend "$BACKEND_PORT" \
  "$ROOT_DIR/backend/.venv/bin/python" manage.py runserver "127.0.0.1:$BACKEND_PORT" --noreload

# ---- 启动前端 ----
cd "$ROOT_DIR/frontend"
start_one frontend "$FRONTEND_PORT" \
  "$ROOT_DIR/frontend/node_modules/.bin/vite" --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort

# ---- 健康检查 ----
log "等待服务就绪…"
backend_ok=0
for _ in $(seq 1 20); do
  if curl -fsS --max-time 2 "http://127.0.0.1:$BACKEND_PORT/healthz/" >/dev/null 2>&1; then
    backend_ok=1
    break
  fi
  sleep 1
done

frontend_ok=0
for _ in $(seq 1 20); do
  if curl -fsS --max-time 2 -o /dev/null "http://127.0.0.1:$FRONTEND_PORT/"; then
    frontend_ok=1
    break
  fi
  sleep 1
done

echo
[[ "$backend_ok" == "1" ]] \
  && log "后端就绪：http://127.0.0.1:$BACKEND_PORT/healthz/ （API 文档 /api/docs/）" \
  || log "后端未通过健康检查，请查看 .dev/backend.log"
[[ "$frontend_ok" == "1" ]] \
  && log "前端就绪：http://127.0.0.1:$FRONTEND_PORT/" \
  || log "前端未就绪，请查看 .dev/frontend.log"
log "停止服务：./scripts/dev-stop.sh"
