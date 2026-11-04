#!/usr/bin/env bash
# 备份数据库与媒体文件，保留 30 天
set -euo pipefail

ENV_FILE="${ENV_FILE:-/srv/guda/env/.env}"
BACKUP_DIR="${BACKUP_DIR:-/srv/guda/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
MEDIA_DIR="${MEDIA_DIR:-/srv/guda/media}"
STAMP="$(date +%Y%m%d-%H%M%S)"
VERSION="$(git -C "${APP_DIR:-/srv/guda/app}" rev-parse --short HEAD 2>/dev/null || echo unknown)"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[backup] 环境文件不存在：$ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

mkdir -p "$BACKUP_DIR"

# localhost 使用本地 socket 认证；其他地址走 TCP
if [[ "${DB_HOST:-127.0.0.1}" == "localhost" ]]; then
  CONN_ARGS=()
else
  CONN_ARGS=(-h "${DB_HOST:-127.0.0.1}" -P "${DB_PORT:-3306}")
fi

echo "[backup] 导出数据库 $DB_NAME"
mysqldump \
  --single-transaction \
  --routines \
  --triggers \
  --default-character-set=utf8mb4 \
  ${CONN_ARGS[@]+"${CONN_ARGS[@]}"} \
  -u "$DB_USER" \
  ${DB_PASSWORD:+-p"$DB_PASSWORD"} \
  "$DB_NAME" | gzip > "$BACKUP_DIR/db-$STAMP-$VERSION.sql.gz"

if [[ -d "$MEDIA_DIR" ]]; then
  echo "[backup] 打包媒体文件"
  tar -czf "$BACKUP_DIR/media-$STAMP-$VERSION.tar.gz" -C "$(dirname "$MEDIA_DIR")" "$(basename "$MEDIA_DIR")"
fi

echo "[backup] 清理 $RETENTION_DAYS 天前的备份"
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'db-*.sql.gz' -mtime +"$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'media-*.tar.gz' -mtime +"$RETENTION_DAYS" -delete

echo "[backup] 完成：$BACKUP_DIR/db-$STAMP-$VERSION.sql.gz"
