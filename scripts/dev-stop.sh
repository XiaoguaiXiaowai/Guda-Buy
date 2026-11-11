#!/usr/bin/env bash
# 停止 dev-start.sh 启动的前后端进程（只处理 .dev/*.pid 中记录的进程）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.dev"

log() { echo "[dev] $*"; }

stop_one() {
  local name="$1" pid_file="$RUN_DIR/$1.pid"

  if [[ ! -f "$pid_file" ]]; then
    log "$name 无 PID 记录，跳过"
    return 0
  fi

  local pid
  pid="$(cat "$pid_file")"
  if ! kill -0 "$pid" 2>/dev/null; then
    log "$name 进程（PID ${pid}）已不存在，清理 PID 文件"
    rm -f "$pid_file"
    return 0
  fi

  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 10); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
  done

  if kill -0 "$pid" 2>/dev/null; then
    log "$name（PID ${pid}）未响应 SIGTERM，发送 SIGKILL"
    kill -9 "$pid" 2>/dev/null || true
  fi

  rm -f "$pid_file"
  log "$name 已停止"
}

stop_one frontend
stop_one backend

for port in 5173 8000; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    log "提示：端口 $port 仍被占用（可能是手动启动的进程）：lsof -nP -iTCP:$port -sTCP:LISTEN"
  fi
done
