#!/usr/bin/env bash
# 恢复数据库或媒体文件
# 用法：FORCE=1 ./restore.sh db  backups/db-20261104-120000.sql.gz
#      FORCE=1 ./restore.sh media backups/media-20261104-120000.tar.gz
set -euo pipefail

ENV_FILE="${ENV_FILE:-/srv/guda/env/.env}"
MEDIA_DIR="${MEDIA_DIR:-/srv/guda/media}"
KIND="${1:-}"
FILE="${2:-}"

if [[ -z "$KIND" || -z "$FILE" || ! -f "$FILE" ]]; then
  echo "用法：FORCE=1 $0 <db|media> <备份文件>" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ "${FORCE:-0}" != "1" ]]; then
  read -r -p "将覆盖 $KIND（数据库 $DB_NAME / 媒体目录 $MEDIA_DIR），确认请输入 yes： " ANSWER
  [[ "$ANSWER" == "yes" ]] || { echo "已取消"; exit 1; }
fi

case "$KIND" in
  db)
    if [[ "${DB_HOST:-127.0.0.1}" == "localhost" ]]; then
      CONN_ARGS=()
    else
      CONN_ARGS=(-h "${DB_HOST:-127.0.0.1}" -P "${DB_PORT:-3306}")
    fi
    echo "[restore] 恢复数据库 $DB_NAME ← $FILE"
    gunzip -c "$FILE" | mysql \
      ${CONN_ARGS[@]+"${CONN_ARGS[@]}"} \
      -u "$DB_USER" \
      ${DB_PASSWORD:+-p"$DB_PASSWORD"} \
      "$DB_NAME"
    ;;
  media)
    echo "[restore] 恢复媒体文件 ← $FILE"
    mkdir -p "$(dirname "$MEDIA_DIR")"
    tar -xzf "$FILE" -C "$(dirname "$MEDIA_DIR")"
    ;;
  *)
    echo "未知类型：$KIND（仅支持 db/media）" >&2
    exit 1
    ;;
esac

echo "[restore] 完成。请重启服务：sudo systemctl restart guda-web guda-celery"
