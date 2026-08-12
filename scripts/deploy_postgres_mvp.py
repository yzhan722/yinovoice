#!/usr/bin/env python3
"""Deploy PostgreSQL MVP to 8.215.80.82 (Docker on 127.0.0.1:5433)."""

from __future__ import annotations

import os
import sys
import tarfile
import tempfile
from pathlib import Path

import paramiko

HOST = os.environ.get("BT_HOST", "8.215.80.82")
PASSWORD = os.environ.get("BT_PASSWORD", "")
ROOT = Path(__file__).resolve().parents[1]
OPT = "/opt/yino-vapi"
DATABASE_URL = (
    "postgresql+asyncpg://yino:yino@127.0.0.1:5433/yino_platform"
)


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 300) -> str:
    print(f"$ {cmd[:200]}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip()[-6000:])
    if err.strip():
        print(err.rstrip()[-2000:], file=sys.stderr)
    if code != 0:
        raise RuntimeError(f"remote failed ({code})")
    return out


def main() -> None:
    if not PASSWORD:
        raise SystemExit("BT_PASSWORD required")

    paths = [
        ROOT / "docker-compose.server.yml",
        ROOT / "platform-api/pyproject.toml",
        ROOT / "platform-api/alembic.ini",
        ROOT / "platform-api/README.md",
        ROOT / "platform-api/.env.example",
        ROOT / "platform-api/migrations",
        ROOT / "platform-api/src/yino_platform_api/app.py",
        ROOT / "platform-api/src/yino_platform_api/config.py",
        ROOT / "platform-api/src/yino_platform_api/db",
        ROOT
        / "platform-api/src/yino_platform_api/repositories/customer_services.py",
        ROOT / "platform-api/src/yino_platform_api/repositories/postgres",
        ROOT / "platform-api/src/yino_platform_api/routes/customer_services.py",
        ROOT / "platform-api/scripts/smoke_postgres_persistence.py",
    ]
    for path in paths:
        if not path.exists():
            raise SystemExit(f"missing {path}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        HOST,
        username="root",
        password=PASSWORD,
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tar_path = Path(tmp.name)
    try:
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(
                ROOT / "docker-compose.server.yml",
                arcname="docker-compose.server.yml",
            )
            tar.add(
                ROOT / "platform-api/pyproject.toml",
                arcname="platform-api/pyproject.toml",
            )
            tar.add(
                ROOT / "platform-api/alembic.ini",
                arcname="platform-api/alembic.ini",
            )
            tar.add(
                ROOT / "platform-api/README.md",
                arcname="platform-api/README.md",
            )
            tar.add(
                ROOT / "platform-api/.env.example",
                arcname="platform-api/.env.example",
            )
            tar.add(
                ROOT / "platform-api/migrations",
                arcname="platform-api/migrations",
            )
            tar.add(
                ROOT / "platform-api/src/yino_platform_api/app.py",
                arcname="platform-api/src/yino_platform_api/app.py",
            )
            tar.add(
                ROOT / "platform-api/src/yino_platform_api/config.py",
                arcname="platform-api/src/yino_platform_api/config.py",
            )
            tar.add(
                ROOT / "platform-api/src/yino_platform_api/db",
                arcname="platform-api/src/yino_platform_api/db",
            )
            tar.add(
                ROOT
                / "platform-api/src/yino_platform_api/repositories/customer_services.py",
                arcname=(
                    "platform-api/src/yino_platform_api/repositories/"
                    "customer_services.py"
                ),
            )
            tar.add(
                ROOT / "platform-api/src/yino_platform_api/repositories/postgres",
                arcname="platform-api/src/yino_platform_api/repositories/postgres",
            )
            tar.add(
                ROOT / "platform-api/src/yino_platform_api/routes/customer_services.py",
                arcname="platform-api/src/yino_platform_api/routes/customer_services.py",
            )
            tar.add(
                ROOT / "platform-api/scripts/smoke_postgres_persistence.py",
                arcname="platform-api/scripts/smoke_postgres_persistence.py",
            )

        remote_tar = "/tmp/yino-postgres-mvp.tar.gz"
        sftp = ssh.open_sftp()
        print(f"upload {tar_path.stat().st_size} bytes")
        sftp.put(str(tar_path), remote_tar)
        sftp.close()

        run(
            ssh,
            rf"""
set -euo pipefail
OPT={OPT}
rm -rf /tmp/yino-pg-mvp
mkdir -p /tmp/yino-pg-mvp
tar -xzf {remote_tar} -C /tmp/yino-pg-mvp
cp -f /tmp/yino-pg-mvp/docker-compose.server.yml "$OPT/docker-compose.postgres.yml"
mkdir -p "$OPT/platform-api/migrations/versions"
mkdir -p "$OPT/platform-api/src/yino_platform_api/db"
mkdir -p "$OPT/platform-api/src/yino_platform_api/repositories/postgres"
mkdir -p "$OPT/platform-api/scripts"
cp -f /tmp/yino-pg-mvp/platform-api/pyproject.toml "$OPT/platform-api/"
cp -f /tmp/yino-pg-mvp/platform-api/alembic.ini "$OPT/platform-api/"
cp -f /tmp/yino-pg-mvp/platform-api/README.md "$OPT/platform-api/"
cp -f /tmp/yino-pg-mvp/platform-api/.env.example "$OPT/platform-api/"
cp -a /tmp/yino-pg-mvp/platform-api/migrations/. "$OPT/platform-api/migrations/"
cp -f /tmp/yino-pg-mvp/platform-api/src/yino_platform_api/app.py \
  "$OPT/platform-api/src/yino_platform_api/"
cp -f /tmp/yino-pg-mvp/platform-api/src/yino_platform_api/config.py \
  "$OPT/platform-api/src/yino_platform_api/"
cp -a /tmp/yino-pg-mvp/platform-api/src/yino_platform_api/db/. \
  "$OPT/platform-api/src/yino_platform_api/db/"
cp -f /tmp/yino-pg-mvp/platform-api/src/yino_platform_api/repositories/customer_services.py \
  "$OPT/platform-api/src/yino_platform_api/repositories/"
cp -a /tmp/yino-pg-mvp/platform-api/src/yino_platform_api/repositories/postgres/. \
  "$OPT/platform-api/src/yino_platform_api/repositories/postgres/"
cp -f /tmp/yino-pg-mvp/platform-api/src/yino_platform_api/routes/customer_services.py \
  "$OPT/platform-api/src/yino_platform_api/routes/"
cp -f /tmp/yino-pg-mvp/platform-api/scripts/smoke_postgres_persistence.py \
  "$OPT/platform-api/scripts/"

# Start dedicated Yino Postgres on 127.0.0.1:5433 (avoid booking :5432).
cd "$OPT"
docker compose -f docker-compose.postgres.yml up -d
for i in $(seq 1 30); do
  if docker compose -f docker-compose.postgres.yml exec -T postgres \
      pg_isready -U yino -d yino_platform >/dev/null 2>&1; then
    echo postgres_ready
    break
  fi
  sleep 2
done
docker compose -f docker-compose.postgres.yml ps

# Ensure DATABASE_URL in EnvironmentFile (do not print secrets).
ENV_FILE="$OPT/config/platform-api.env"
if ! grep -q '^DATABASE_URL=' "$ENV_FILE"; then
  printf '\nDATABASE_URL=%s\n' '{DATABASE_URL}' >> "$ENV_FILE"
  echo database_url_appended
else
  # Replace existing DATABASE_URL line for this Demo target.
  sed -i 's|^DATABASE_URL=.*|DATABASE_URL={DATABASE_URL}|' "$ENV_FILE"
  echo database_url_updated
fi
grep -E '^(LIVEKIT_|CALL_|DATABASE_URL=)' "$ENV_FILE" | sed 's/=.*/=***/' 

cd "$OPT/platform-api"
PY="$OPT/platform-api/.venv/bin/python"
"$PY" -m ensurepip --upgrade
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q 'sqlalchemy[asyncio]>=2.0,<3' 'asyncpg>=0.30,<1' 'alembic>=1.14,<2'
"$PY" -m pip install -q -e .
export DATABASE_URL='{DATABASE_URL}'
"$PY" -m alembic upgrade head
systemctl restart yino-platform-api
sleep 3
systemctl is-active yino-platform-api yino-voice-agent yino-livekit

# HTTP smoke against local API
python3 - <<'PY'
import json, urllib.request
from uuid import UUID

TENANT = '00000000-0000-0000-0000-000000000001'
CS = '00000000-0000-0000-0000-000000000101'
headers = {{'X-Tenant-ID': TENANT}}

def get(path):
    req = urllib.request.Request('http://127.0.0.1:8000' + path, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)

health = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=10)
assert health.status == 200
cs = get(f'/api/v1/customer-services/{{CS}}')
assert cs['id'] == CS
assert cs['voice']['tts_voice']
assert 'platform_prompt' in cs
print('api_ok', 'tts', cs['voice']['tts_voice'], 'version', cs['version'])
PY

rm -rf /tmp/yino-pg-mvp {remote_tar}
echo deployed_postgres_mvp
""",
            timeout=420,
        )
    finally:
        tar_path.unlink(missing_ok=True)
        ssh.close()
    print("deployed")


if __name__ == "__main__":
    main()
