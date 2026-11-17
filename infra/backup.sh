#!/usr/bin/env bash
# Daily backup: database dump + uploaded files, with old copies pruned.
#
#   infra/backup.sh [backup-dir] [days-to-keep]     (defaults: ./backups, 14)
#
# Run it from the repository folder on the server. Schedule it with cron (see docs/DEPLOYMENT.md)
# and copy the backup folder off the server (rclone, restic, your provider's object storage).
set -euo pipefail

cd "$(dirname "$0")/.."
export COMPOSE_FILE="${COMPOSE_FILE:-compose.yaml:compose.prod.yaml}"
dest="$(mkdir -p "${1:-backups}" && cd "${1:-backups}" && pwd)"
keep_days="${2:-14}"
stamp="$(date +%F-%H%M)"

# Write to temporary names first so a failed run never leaves a half-written "good" backup.
docker compose exec -T postgres pg_dump -U postgres -Fc citebase > "$dest/.db-$stamp.dump"
docker compose run --rm --no-deps -T -u root -v "$dest":/backup --entrypoint sh api \
  -c "tar -czf /backup/.storage-$stamp.tgz -C /data/storage ."
mv "$dest/.db-$stamp.dump" "$dest/db-$stamp.dump"
mv "$dest/.storage-$stamp.tgz" "$dest/storage-$stamp.tgz"

find "$dest" -maxdepth 1 -type f \( -name 'db-*.dump' -o -name 'storage-*.tgz' \) -mtime "+$keep_days" -delete
find "$dest" -maxdepth 1 -type f -name '.*' -mmin +1440 -delete  # leftovers of failed runs

echo "backup written: $dest/db-$stamp.dump, $dest/storage-$stamp.tgz (keeping $keep_days days)"
