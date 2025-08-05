#!/usr/bin/env bash
set -euo pipefail

# Default: hourly (3600 seconds)
# Accept either BACKUP_INTERVAL (preferred) or legacy BACKUP_SCHEDULE for compatibility
BACKUP_INTERVAL=${BACKUP_INTERVAL:-${BACKUP_SCHEDULE:-3600}}

function backup_once() {
  # Generate a fresh timestamped file name each run
  local dump_name
  dump_name="audit_$(date +%F_%H%M%S).sql.gz"
  local remote="${BACKUP_PROVIDER:-s3}:${BACKUP_BUCKET:-acp-audit-backups}/${dump_name}"

  echo "[db-backup] Starting dump to $remote"
  pg_dump -h "$PG_HOST" -U "$PG_USER" -d "$PG_DB" -Z9 | rclone rcat "$remote"
  echo "[db-backup] Backup complete"
}

# Ensure pg_dump can auth non-interactively
export PGPASSWORD="${PG_PASSWORD:-}"

while true; do
  backup_once || echo "[db-backup] Backup failed"
  sleep "$BACKUP_INTERVAL"
done
