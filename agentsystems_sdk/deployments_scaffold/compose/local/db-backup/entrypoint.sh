#!/usr/bin/env bash
#
# Database backup service entrypoint
# Performs periodic PostgreSQL backups to cloud storage via rclone
#
# Required environment variables:
#   PG_HOST     - PostgreSQL host
#   PG_USER     - PostgreSQL user
#   PG_DB       - PostgreSQL database name
#   PG_PASSWORD - PostgreSQL password
#
# Optional environment variables:
#   BACKUP_INTERVAL  - Seconds between backups (default: 3600)
#   BACKUP_SCHEDULE  - Legacy alias for BACKUP_INTERVAL
#   BACKUP_PROVIDER  - Rclone remote name (default: s3)
#   BACKUP_BUCKET    - Bucket/container name (default: acp-audit-backups)
#
set -euo pipefail

# Default: hourly (3600 seconds)
# Accept either BACKUP_INTERVAL (preferred) or legacy BACKUP_SCHEDULE for compatibility
readonly BACKUP_INTERVAL="${BACKUP_INTERVAL:-${BACKUP_SCHEDULE:-3600}}"

# Validate required environment variables
validate_environment() {
    local missing_vars=()

    [[ -z "${PG_HOST:-}" ]] && missing_vars+=("PG_HOST")
    [[ -z "${PG_USER:-}" ]] && missing_vars+=("PG_USER")
    [[ -z "${PG_DB:-}" ]] && missing_vars+=("PG_DB")
    [[ -z "${PG_PASSWORD:-}" ]] && missing_vars+=("PG_PASSWORD")

    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        echo "[db-backup] ERROR: Missing required environment variables: ${missing_vars[*]}" >&2
        exit 1
    fi
}

# Perform a single backup
backup_once() {
    # Generate a fresh timestamped file name each run
    local dump_name
    dump_name="audit_$(date +%F_%H%M%S).sql.gz"
    local remote="${BACKUP_PROVIDER:-s3}:${BACKUP_BUCKET:-acp-audit-backups}/${dump_name}"

    echo "[db-backup] Starting dump to ${remote}"

    # Use pipefail to catch errors in the pipeline
    if pg_dump -h "${PG_HOST}" -U "${PG_USER}" -d "${PG_DB}" -Z9 | rclone rcat "${remote}"; then
        echo "[db-backup] Backup complete: ${dump_name}"
        return 0
    else
        echo "[db-backup] ERROR: Backup failed for ${dump_name}" >&2
        return 1
    fi
}

# Main execution
main() {
    # Validate environment on startup
    validate_environment

    # Ensure pg_dump can auth non-interactively
    export PGPASSWORD="${PG_PASSWORD}"

    echo "[db-backup] Starting backup service (interval: ${BACKUP_INTERVAL}s)"

    # Main backup loop
    while true; do
        if ! backup_once; then
            echo "[db-backup] WARNING: Backup failed, will retry in ${BACKUP_INTERVAL} seconds" >&2
        fi
        sleep "${BACKUP_INTERVAL}"
    done
}

# Execute main function
main "$@"
