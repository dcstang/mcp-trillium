#!/usr/bin/env bash
# Backup the Trilium Docker volume to a local directory and a rclone remote.
# Designed to be called from cron; exits non-zero on any failure.
#
# Required env / defaults:
#   TRILIUM_VOLUME_NAME  — Docker volume name            (default: trilium_data)
#   BACKUP_DIR           — Local directory for archives  (default: /opt/backups/trilium)
#   RCLONE_REMOTE        — rclone destination path       (default: remote:trilium-backups)
#   RETENTION_DAYS       — Days to keep local archives   (default: 7)
#
# Cron example (runs at 03:00 daily):
#   0 3 * * * /opt/mcp-trillium/backup.sh >> /var/log/trilium-backup.log 2>&1

set -euo pipefail

TRILIUM_VOLUME="${TRILIUM_VOLUME_NAME:-trilium_data}"
BACKUP_DIR="${BACKUP_DIR:-/opt/backups/trilium}"
RCLONE_REMOTE="${RCLONE_REMOTE:-remote:trilium-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
DATE=$(date +%Y%m%d_%H%M%S)
ARCHIVE="${BACKUP_DIR}/trilium_${DATE}.tar.gz"

echo "[$(date -Iseconds)] Starting backup of volume '${TRILIUM_VOLUME}'"

mkdir -p "$BACKUP_DIR"

# Snapshot the volume via a throwaway alpine container (read-only mount).
docker run --rm \
  -v "${TRILIUM_VOLUME}:/data:ro" \
  -v "${BACKUP_DIR}:/backup" \
  alpine tar czf "/backup/trilium_${DATE}.tar.gz" -C /data .

echo "[$(date -Iseconds)] Archive created: ${ARCHIVE}"

# Push to rclone remote.
rclone copy "$ARCHIVE" "$RCLONE_REMOTE"
echo "[$(date -Iseconds)] Uploaded to ${RCLONE_REMOTE}"

# Prune old local archives.
find "$BACKUP_DIR" -name "*.tar.gz" -mtime "+${RETENTION_DAYS}" -delete
echo "[$(date -Iseconds)] Pruned archives older than ${RETENTION_DAYS} days"

echo "[$(date -Iseconds)] Backup complete: ${ARCHIVE}"
