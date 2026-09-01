#!/usr/bin/env bash
set -euo pipefail
umask 077

database_path="${SQLITE_PATH:-/var/lib/vapi-call-insights/runtime.sqlite}"
backup_directory="${BACKUP_DIRECTORY:-/var/backups/vapi-call-insights}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_path="${backup_directory}/runtime-${timestamp}.sqlite"
partial_path="${backup_path}.partial.$$"

install -d -m 0700 -o root -g root "$backup_directory"
chmod 700 "$backup_directory"
trap 'rm -f "$partial_path"' EXIT

sqlite3 "$database_path" ".backup \"$partial_path\""
chmod 600 "$partial_path"

verification="$(sqlite3 -readonly "$partial_path" "PRAGMA quick_check;")"
if [[ "$verification" != "ok" ]]; then
  echo "runtime_backup_failed" >&2
  exit 1
fi
mv "$partial_path" "$backup_path"
trap - EXIT

find "$backup_directory" -type f -name 'runtime-*.sqlite' -mtime +30 -delete
echo "runtime_backup_ok"
