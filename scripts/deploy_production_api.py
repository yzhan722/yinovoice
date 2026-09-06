#!/usr/bin/env python3
"""Deploy the Platform API to production and run Alembic (plan P0.2).

Scope is deliberately backend-only: platform-api source, the additive
migrations, and the console login secrets. The frontend bundle and the
voice-agent that carries live calls are left untouched, so this window cannot
change what callers hear. Every existing route stays backward compatible, so
the currently deployed frontend keeps working against the new API.

Order: backup source + dump database -> upload source -> alembic upgrade head
-> provision AUTH_SECRET / admin bootstrap -> restart -> verify. Rollback
commands are printed at the end.

Environment:
    BT_HOST, BT_USER, BT_PASSWORD          server access
    PLATFORM_ADMIN_ACCOUNT/PASSWORD        optional console bootstrap
Usage:
    python scripts/deploy_production_api.py --dry-run   # print the plan
    python scripts/deploy_production_api.py
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import paramiko

HOST = os.environ.get("BT_HOST", "8.215.80.82")
USER = os.environ.get("BT_USER", "root")
PASSWORD = os.environ.get("BT_PASSWORD", "")
ADMIN_ACCOUNT = os.environ.get("PLATFORM_ADMIN_ACCOUNT", "")
ADMIN_PASSWORD = os.environ.get("PLATFORM_ADMIN_PASSWORD", "")

ROOT = "/opt/yino-vapi"
API_SERVICE = "yino-platform-api"
POSTGRES_CONTAINER = os.environ.get("YINO_POSTGRES_CONTAINER", "yino-platform-postgres")
LOCAL_PLATFORM = Path(__file__).resolve().parents[1] / "apps/control-plane/api"
STAMP = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
SKIP_PARTS = {".venv", "__pycache__", ".pytest_cache", "node_modules", "dist"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not (LOCAL_PLATFORM / "src").is_dir():
        return fail(f"missing {LOCAL_PLATFORM / 'src'}")
    if args.dry_run:
        print(
            "PLAN\n"
            f"  1. backup {ROOT}/platform-api/src -> src.bak-{STAMP}\n"
            f"  2. pg_dump yino_platform -> {ROOT}/backups/\n"
            f"  3. upload {LOCAL_PLATFORM} -> {ROOT}/platform-api\n"
            "  4. alembic upgrade head (20260901_0012, 20260903_0013: both additive)\n"
            "  5. set AUTH_SECRET + optional PLATFORM_ADMIN_* (SFTP, no echo)\n"
            f"  6. systemctl restart {API_SERVICE}\n"
            "  7. verify /health, existing routes, admin routes\n"
            "  frontend-dist and voice-agent are NOT touched"
        )
        return 0
    if not PASSWORD:
        return fail("BT_PASSWORD is required")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting {USER}@{HOST} ...")
    ssh.connect(
        HOST,
        username=USER,
        password=PASSWORD,
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )
    ssh.get_transport().set_keepalive(15)

    before = run(
        ssh,
        "pre-flight",
        f"""
set -e
curl -s -o /dev/null -w 'health:%{{http_code}}\\n' http://127.0.0.1:8000/health
docker exec {POSTGRES_CONTAINER} psql -U yino -tAc "select version_num from alembic_version" -d yino_platform
curl -s http://127.0.0.1:8000/openapi.json | python3 -c "import json,sys; print('routes:', len(json.load(sys.stdin)['paths']))"
systemctl is-active {API_SERVICE}
""",
    )
    if "health:200" not in before:
        ssh.close()
        return fail("production API is not healthy; aborting before any change")

    run(
        ssh,
        "backup source and database",
        f"""
set -e
mkdir -p {ROOT}/backups
cp -a {ROOT}/platform-api/src {ROOT}/platform-api/src.bak-{STAMP}
echo "SRC_BACKUP={ROOT}/platform-api/src.bak-{STAMP}"
DUMP={ROOT}/backups/yino_platform-{STAMP}.sql
docker exec {POSTGRES_CONTAINER} pg_dump -U yino -d yino_platform > "$DUMP"
gzip -f "$DUMP"
ls -la "$DUMP.gz"
""",
    )

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tar_path = Path(tmp.name)
    try:
        with tarfile.open(tar_path, "w:gz") as tar:
            for path in (LOCAL_PLATFORM).rglob("*"):
                if not path.is_file() or path.suffix == ".pyc":
                    continue
                if any(part in SKIP_PARTS for part in path.parts):
                    continue
                if path.name.startswith(".env") and path.name != ".env.example":
                    continue
                rel = path.relative_to(LOCAL_PLATFORM).as_posix()
                tar.add(path, arcname=f"platform-api/{rel}")
        sftp = ssh.open_sftp()
        remote_tar = "/tmp/yino-platform-api.tar.gz"
        print(f"Uploading {tar_path.stat().st_size // 1024} KB -> {remote_tar}")
        sftp.put(str(tar_path), remote_tar)
        sftp.close()
    finally:
        tar_path.unlink(missing_ok=True)

    # Replace tracked source only; .venv and config stay where they are.
    run(
        ssh,
        "unpack source",
        f"""
set -e
rm -rf {ROOT}/platform-api/src {ROOT}/platform-api/migrations {ROOT}/platform-api/tests
tar -xzf {remote_tar} -C {ROOT} && rm -f {remote_tar}
find {ROOT}/platform-api/src -name __pycache__ -type d -prune -exec rm -rf {{}} + 2>/dev/null || true
ls {ROOT}/platform-api/migrations/versions/ | tail -3
""",
    )

    sftp = ssh.open_sftp()
    added = upsert_env_secrets(
        sftp,
        f"{ROOT}/config/platform-api.env",
        {
            "AUTH_SECRET": secrets.token_urlsafe(32),
            "PLATFORM_ADMIN_ACCOUNT": ADMIN_ACCOUNT,
            "PLATFORM_ADMIN_PASSWORD": ADMIN_PASSWORD,
        },
    )
    sftp.close()
    print(f"env keys added: {added or 'none (already present)'}")

    run(
        ssh,
        "alembic upgrade head",
        f"""
set -e
cd {ROOT}/platform-api
set -a
. {ROOT}/config/platform-api.env
set +a
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic current
""",
    )

    run(
        ssh,
        "restart API",
        f"""
systemctl restart {API_SERVICE}
sleep 4
systemctl is-active {API_SERVICE}
""",
    )

    after = run(
        ssh,
        "verify",
        f"""
curl -s -o /dev/null -w 'health:%{{http_code}}\\n' http://127.0.0.1:8000/health
curl -s -o /dev/null -w 'instances:%{{http_code}}\\n' -H 'X-Tenant-ID: 00000000-0000-0000-0000-000000000001' http://127.0.0.1:8000/api/v1/customer-services
curl -s -o /dev/null -w 'calls:%{{http_code}}\\n' -H 'X-Tenant-ID: 00000000-0000-0000-0000-000000000001' http://127.0.0.1:8000/api/v1/call-records
curl -s -o /dev/null -w 'admin_no_token:%{{http_code}}\\n' http://127.0.0.1:8000/api/v1/admin/tenants
curl -sk -o /dev/null -w 'site:%{{http_code}}\\n' -H 'Host: {HOST}' https://127.0.0.1/
curl -s http://127.0.0.1:8000/openapi.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('routes:', len(d['paths'])); print('has_admin:', any(p.startswith('/api/v1/admin') for p in d['paths']))"
docker exec {POSTGRES_CONTAINER} psql -U yino -tAc "select version_num from alembic_version" -d yino_platform
docker exec {POSTGRES_CONTAINER} psql -U yino -tAc "select count(*) from voice_agent_instances" -d yino_platform
docker exec {POSTGRES_CONTAINER} psql -U yino -tAc "select count(*) from call_records" -d yino_platform
systemctl is-active {API_SERVICE} yino-voice-agent yino-livekit | tr '\\n' ' '; echo
""",
        check=False,
    )

    ok = "health:200" in after and "has_admin: True" in after
    print("\n" + ("DEPLOY_OK" if ok else "DEPLOY_NEEDS_REVIEW"))
    print(
        "Rollback (source + schema):\n"
        f"  rm -rf {ROOT}/platform-api/src && "
        f"mv {ROOT}/platform-api/src.bak-{STAMP} {ROOT}/platform-api/src\n"
        f"  cd {ROOT}/platform-api && set -a && . {ROOT}/config/platform-api.env && set +a && "
        ".venv/bin/python -m alembic downgrade 20260825_0011\n"
        f"  systemctl restart {API_SERVICE}\n"
        f"  full restore: gunzip -c {ROOT}/backups/yino_platform-{STAMP}.sql.gz | "
        f"docker exec -i {POSTGRES_CONTAINER} psql -U yino -d yino_platform"
    )
    ssh.close()
    return 0 if ok else 1


def run(ssh, title, cmd, check=True, limit=4000, timeout=900):
    print(f"\n===== {title} =====")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    text = (out + (("\n[stderr] " + err) if err.strip() else "")).strip()
    print(text[:limit] or "(empty)")
    if check and code != 0:
        raise RuntimeError(f"step failed ({code}): {title}")
    return out


def upsert_env_secrets(sftp, path, values):
    """Set missing keys in a remote env file over SFTP (never via a command)."""
    try:
        with sftp.file(path, "r") as handle:
            lines = handle.read().decode("utf-8").splitlines()
    except OSError:
        lines = []
    present = {
        line.split("=", 1)[0].strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#") and "=" in line
    }
    added = []
    for key, value in values.items():
        if key in present or not value:
            continue
        lines.append(f"{key}={value}")
        added.append(key)
    if added:
        with sftp.file(path, "w") as handle:
            handle.write("\n".join(lines) + "\n")
        sftp.chmod(path, 0o600)
    return added


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
