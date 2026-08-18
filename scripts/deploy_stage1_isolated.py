#!/usr/bin/env python3
"""Deploy yinovoice apps/ as an isolated /stage1 stack on the server.

Source of truth (local monorepo):
  - apps/control-plane/api
  - apps/runtime/voice-agent
  - apps/control-plane/web/dist  (build with VITE_BASE_URL=/stage1/)

Behavior:
  - Installs parallel platform-api (:8011) + voice-agent (agent name stage1)
  - Serves frontend at https://HOST/stage1/ (existing 443, no new SG port)
  - Does NOT modify /opt/yino-vapi production code, frontend, or backups
  - Does NOT restore or overwrite production frontend
  - Stage1 uses a separate Postgres database on the shared Docker instance
    (default name yino_platform_stage1), never the production database name
"""
from __future__ import annotations

import os
import sys
import tarfile
import tempfile
from pathlib import Path

import paramiko

HOST = os.environ.get("BT_HOST", "8.215.80.82")
USER = os.environ.get("BT_USER", "root")
PASSWORD = os.environ.get("BT_PASSWORD", "")
REMOTE_ROOT = "/opt/yino-vapi-stage1"
PROD_ROOT = "/opt/yino-vapi"
STAGE_API_PORT = 8011
STAGE_AGENT_NAME = "yino-customer-service-stage1"
STAGE_PREFIX = "/stage1"
STAGE_DATABASE_NAME = os.environ.get("STAGE_DATABASE_NAME", "yino_platform_stage1")
POSTGRES_CONTAINER = os.environ.get(
    "YINO_POSTGRES_CONTAINER", "yino-platform-postgres"
)

LOCAL_ROOT = Path(__file__).resolve().parents[1]
LOCAL_FRONT_DIST = LOCAL_ROOT / "apps" / "control-plane" / "web" / "dist"
LOCAL_PLATFORM = LOCAL_ROOT / "apps" / "control-plane" / "api"
LOCAL_VOICE = LOCAL_ROOT / "apps" / "runtime" / "voice-agent"

REMOTE_NGINX = "/www/server/panel/vhost/nginx/yino-vapi-443.conf"
REMOTE_NGINX_SNIPPET = (
    "/www/server/panel/vhost/nginx/extension/yino-vapi-stage1.conf"
)


def run(ssh: paramiko.SSHClient, cmd: str, check: bool = True) -> str:
    print(f"$ {cmd}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=600)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip())
    if err.strip():
        print(err.rstrip(), file=sys.stderr)
    if check and code != 0:
        raise RuntimeError(f"command failed ({code}): {cmd}")
    return out


def pack_tree(src: Path, arc_root: str, tar: tarfile.TarFile) -> None:
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(src).as_posix()
        if any(
            part in {".venv", "__pycache__", ".pytest_cache", "node_modules", "dist"}
            for part in path.parts
        ):
            continue
        if path.suffix in {".pyc"}:
            continue
        if path.name == ".env.local":
            continue
        tar.add(path, arcname=f"{arc_root}/{rel}")


def write_remote(sftp: paramiko.SFTPClient, path: str, content: str) -> None:
    with sftp.file(path, "w") as handle:
        handle.write(content)


def main() -> None:
    if not PASSWORD:
        raise SystemExit("BT_PASSWORD is required")
    if not LOCAL_FRONT_DIST.is_dir():
        raise SystemExit(f"front dist missing: {LOCAL_FRONT_DIST}")
    for required in (LOCAL_PLATFORM / "src", LOCAL_VOICE / "src"):
        if not required.is_dir():
            raise SystemExit(f"missing {required}")

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

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tar_path = Path(tmp.name)
    try:
        with tarfile.open(tar_path, "w:gz") as tar:
            pack_tree(LOCAL_PLATFORM, "platform-api", tar)
            pack_tree(LOCAL_VOICE, "voice-agent", tar)
            for path in LOCAL_FRONT_DIST.rglob("*"):
                if path.is_file():
                    tar.add(
                        path,
                        arcname=(
                            "frontend-dist/"
                            + path.relative_to(LOCAL_FRONT_DIST).as_posix()
                        ),
                    )

        sftp = ssh.open_sftp()
        remote_tar = "/tmp/yino-vapi-stage1-bundle.tar.gz"
        print(f"Uploading bundle -> {remote_tar}")
        sftp.put(str(tar_path), remote_tar)

        platform_unit = f"""[Unit]
Description=Yino Stage1 Platform API (FastAPI on :{STAGE_API_PORT})
After=network.target yino-livekit.service
Requires=yino-livekit.service

[Service]
Type=simple
WorkingDirectory={REMOTE_ROOT}/platform-api
EnvironmentFile={REMOTE_ROOT}/config/platform-api.env
Environment=PYTHONPATH={REMOTE_ROOT}/platform-api/src
ExecStart={REMOTE_ROOT}/platform-api/.venv/bin/uvicorn yino_platform_api.app:app --host 127.0.0.1 --port {STAGE_API_PORT}
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
"""
        voice_unit = f"""[Unit]
Description=Yino Stage1 Voice Agent (LiveKit worker)
After=network.target yino-platform-api-stage1.service
Requires=yino-platform-api-stage1.service

[Service]
Type=simple
WorkingDirectory={REMOTE_ROOT}/voice-agent
EnvironmentFile={REMOTE_ROOT}/config/voice-agent.env
Environment=PYTHONPATH={REMOTE_ROOT}/voice-agent/src
ExecStart={REMOTE_ROOT}/voice-agent/.venv/bin/python -m yino_voice_agent.server dev
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
"""
        # Inserted via include; keep prod location / untouched.
        nginx_snippet = f"""
# Yino stage1 isolated stack (local worktree deploy)
location ^~ {STAGE_PREFIX}/api/v1/ {{
    proxy_pass http://127.0.0.1:{STAGE_API_PORT}/api/v1/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 60s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
    client_max_body_size 200m;
}}

location ^~ {STAGE_PREFIX}/ {{
    alias {REMOTE_ROOT}/frontend-dist/;
    index index.html;
    add_header Cache-Control "no-cache";
}}
"""
        write_remote(sftp, "/tmp/yino-platform-api-stage1.service", platform_unit)
        write_remote(sftp, "/tmp/yino-voice-agent-stage1.service", voice_unit)
        write_remote(sftp, "/tmp/yino-vapi-stage1.nginx.conf", nginx_snippet)
        sftp.close()

        # Production tree is read-only for this script (config/venv copy only).
        run(ssh, f"mkdir -p {REMOTE_ROOT}/{{config,systemd,data/recordings,logs}}")
        run(
            ssh,
            f"rm -rf {REMOTE_ROOT}/platform-api {REMOTE_ROOT}/voice-agent "
            f"{REMOTE_ROOT}/frontend-dist && "
            f"mkdir -p {REMOTE_ROOT} && "
            f"tar -xzf {remote_tar} -C {REMOTE_ROOT} && rm -f {remote_tar}",
        )

        # Reuse prod venvs (heavy deps) then reinstall editable packages from uploaded src.
        run(
            ssh,
            f"rm -rf {REMOTE_ROOT}/platform-api/.venv && "
            f"cp -a {PROD_ROOT}/platform-api/.venv {REMOTE_ROOT}/platform-api/.venv",
        )
        run(
            ssh,
            f"rm -rf {REMOTE_ROOT}/voice-agent/.venv && "
            f"cp -a {PROD_ROOT}/voice-agent/.venv {REMOTE_ROOT}/voice-agent/.venv",
        )
        # Prod venv is an editable install pointing at /opt/yino-vapi/...; rewrite
        # those .pth entries so Stage1 never silently imports production source.
        run(
            ssh,
            f"""
python3 - <<'PY'
from pathlib import Path
root = Path("{REMOTE_ROOT}")
rewrites = {{
    Path("{PROD_ROOT}/platform-api/src"): root / "platform-api" / "src",
    Path("{PROD_ROOT}/voice-agent/src"): root / "voice-agent" / "src",
}}
for site in root.glob("*/.venv/lib/python*/site-packages"):
    for pth in site.glob("__editable__*.pth"):
        lines = []
        changed = False
        for raw in pth.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            replaced = line
            for old, new in rewrites.items():
                if line == str(old):
                    replaced = str(new)
                    changed = True
                    break
            lines.append(replaced)
        if changed:
            pth.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
            print(f"rewrote {{pth}}")
PY
""",
        )
        # uv venv has no pip; run uploaded src via PYTHONPATH in systemd units.

        # Env: derive secrets from prod files on the server (values not printed).
        # DATABASE_URL is rewritten to STAGE_DATABASE_NAME on the same Postgres.
        run(
            ssh,
            f"""
python3 - <<'PY'
from pathlib import Path
from urllib.parse import urlparse, urlunparse

def load_env(path):
    data = {{}}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data

prod_api = load_env(Path("{PROD_ROOT}/config/platform-api.env"))
prod_va = load_env(Path("{PROD_ROOT}/config/voice-agent.env"))
merged = dict(prod_api)
merged.update(prod_va)

prod_db = prod_api.get("DATABASE_URL", "").strip()
if not prod_db:
    raise SystemExit("production DATABASE_URL missing; cannot derive stage1 DB")
parsed = urlparse(prod_db)
if parsed.path.rstrip("/").split("/")[-1] == "{STAGE_DATABASE_NAME}":
    raise SystemExit("refusing to reuse production database name for stage1")
stage_db = urlunparse(parsed._replace(path="/{STAGE_DATABASE_NAME}"))

def write_env(path, rows):
    path.write_text("\\n".join(rows) + "\\n", encoding="utf-8")
    path.chmod(0o600)

write_env(
    Path("{REMOTE_ROOT}/config/platform-api.env"),
    [
        "LIVEKIT_URL=wss://{HOST}/livekit",
        "LIVEKIT_API_URL=http://127.0.0.1:7880",
        "LIVEKIT_API_KEY=" + merged["LIVEKIT_API_KEY"],
        "LIVEKIT_API_SECRET=" + merged["LIVEKIT_API_SECRET"],
        "LIVEKIT_AGENT_NAME={STAGE_AGENT_NAME}",
        "CALL_RECORDING_DIR={REMOTE_ROOT}/data/recordings",
        "CALL_RECORDING_MAX_BYTES=104857600",
        "DATABASE_URL=" + stage_db,
    ],
)
write_env(
    Path("{REMOTE_ROOT}/config/voice-agent.env"),
    [
        "LIVEKIT_URL=http://127.0.0.1:7880",
        "LIVEKIT_API_KEY=" + merged["LIVEKIT_API_KEY"],
        "LIVEKIT_API_SECRET=" + merged["LIVEKIT_API_SECRET"],
        "LIVEKIT_AGENT_NAME={STAGE_AGENT_NAME}",
        "PLATFORM_API_URL=http://127.0.0.1:{STAGE_API_PORT}",
        "ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV=false",
        "VOICE_PROVIDER_MODE=" + merged.get("VOICE_PROVIDER_MODE", "qwen-realtime"),
        "DASHSCOPE_API_KEY=" + merged["DASHSCOPE_API_KEY"],
        "QWEN_REALTIME_URL=" + merged["QWEN_REALTIME_URL"],
        "QWEN_REALTIME_MODEL=" + merged["QWEN_REALTIME_MODEL"],
        "QWEN_REALTIME_VOICE=" + merged["QWEN_REALTIME_VOICE"],
        "AGENT_LANGUAGE=" + merged.get("AGENT_LANGUAGE", "zh"),
        "AGENT_GREETING=" + merged.get("AGENT_GREETING", "hello"),
    ],
)
print("ENV_WRITTEN")
print("STAGE_DB_NAME={STAGE_DATABASE_NAME}")
PY
""",
        )

        # Create isolated DB (same Docker Postgres) and migrate Stage1 schema.
        run(
            ssh,
            f"""
set -e
# Resolve DB role from production URL without printing secrets.
DB_USER=$(python3 - <<'PY'
from pathlib import Path
from urllib.parse import urlparse, unquote
for line in Path("{PROD_ROOT}/config/platform-api.env").read_text().splitlines():
    if line.startswith("DATABASE_URL="):
        u = urlparse(line.split("=", 1)[1].strip())
        print(unquote(u.username or "yino"))
        break
PY
)
docker exec {POSTGRES_CONTAINER} psql -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 -Atc \
  "SELECT 1 FROM pg_database WHERE datname='{STAGE_DATABASE_NAME}'" | grep -q 1 \
  || docker exec {POSTGRES_CONTAINER} psql -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 -c \
  "CREATE DATABASE {STAGE_DATABASE_NAME} OWNER \\"$DB_USER\\";"
echo STAGE_DB_READY
cd {REMOTE_ROOT}/platform-api
set -a
. {REMOTE_ROOT}/config/platform-api.env
set +a
if [ -x .venv/bin/alembic ]; then
  .venv/bin/alembic upgrade head
elif [ -x .venv/bin/python ]; then
  .venv/bin/python -m alembic upgrade head
else
  echo "alembic missing in stage1 venv" >&2
  exit 1
fi
echo STAGE_MIGRATIONS_OK
""",
        )

        run(
            ssh,
            "cp /tmp/yino-platform-api-stage1.service "
            "/etc/systemd/system/yino-platform-api-stage1.service && "
            "cp /tmp/yino-voice-agent-stage1.service "
            "/etc/systemd/system/yino-voice-agent-stage1.service && "
            f"cp /tmp/yino-platform-api-stage1.service {REMOTE_ROOT}/systemd/ && "
            f"cp /tmp/yino-voice-agent-stage1.service {REMOTE_ROOT}/systemd/ && "
            "rm -f /tmp/yino-platform-api-stage1.service "
            "/tmp/yino-voice-agent-stage1.service",
        )

        # Ensure nginx 443 includes exactly one stage1 block before location /.
        run(
            ssh,
            f"""
set -e
python3 - <<'PY'
from pathlib import Path
conf = Path("{REMOTE_NGINX}")
text = conf.read_text(encoding="utf-8")
marker = "# Yino stage1 isolated stack"
while True:
    start = text.find(marker)
    if start < 0:
        break
    line_start = text.rfind("\\n", 0, start) + 1
    i = start
    while True:
        next_loc = text.find("\\n    location ", i + 1)
        next_access = text.find("\\n    access_log", i + 1)
        candidates = [x for x in (next_loc, next_access) if x >= 0]
        if not candidates:
            end = len(text)
            break
        end = min(candidates)
        window = text[end:end + 120]
        if "/stage1" in window or "Yino stage1" in window:
            i = end
            continue
        break
    text = text[:line_start] + text[end + 1:]

snippet = Path("/tmp/yino-vapi-stage1.nginx.conf").read_text(encoding="utf-8").rstrip() + "\\n\\n"
indented = "\\n".join(("    " + line if line.strip() else line) for line in snippet.splitlines()) + "\\n\\n"
needle = "    # 前端静态"
idx = text.find(needle)
if idx < 0:
    idx = text.find("    location / {{")
if idx < 0:
    raise SystemExit("cannot find insertion point in nginx conf")
text = text[:idx] + indented + text[idx:]
conf.write_text(text, encoding="utf-8")
print("NGINX_STAGE1_UPSERTED")
print("markers", text.count(marker))
PY
rm -f /tmp/yino-vapi-stage1.nginx.conf
""",
        )

        nginx_bin = "/www/server/nginx/sbin/nginx"
        run(ssh, f"test -x {nginx_bin} && {nginx_bin} -t || nginx -t")
        run(
            ssh,
            f"test -x {nginx_bin} && {nginx_bin} -s reload || "
            "(systemctl reload nginx || service nginx reload)",
        )

        run(ssh, "systemctl daemon-reload")
        run(
            ssh,
            "systemctl enable yino-platform-api-stage1.service "
            "yino-voice-agent-stage1.service",
            check=False,
        )
        run(
            ssh,
            "systemctl restart yino-platform-api-stage1.service && "
            "systemctl restart yino-voice-agent-stage1.service",
        )
        run(ssh, "sleep 2")
        run(
            ssh,
            "systemctl is-active yino-platform-api-stage1.service "
            "yino-voice-agent-stage1.service "
            "yino-platform-api.service yino-voice-agent.service",
            check=False,
        )
        run(
            ssh,
            f"ss -lntp | grep -E ':(8000|{STAGE_API_PORT})\\b' || true",
            check=False,
        )
        run(
            ssh,
            "curl -sk -o /dev/null -w 'prod_front:%{http_code}\\n' "
            f"-H 'Host: {HOST}' https://127.0.0.1/",
            check=False,
        )
        run(
            ssh,
            "curl -sk -o /dev/null -w 'stage_front:%{http_code}\\n' "
            f"-H 'Host: {HOST}' https://127.0.0.1{STAGE_PREFIX}/",
            check=False,
        )
        run(
            ssh,
            "curl -sk -o /dev/null -w 'stage_list:%{http_code}\\n' "
            f"-H 'Host: {HOST}' "
            "-H 'X-Tenant-ID: 00000000-0000-0000-0000-000000000001' "
            f"https://127.0.0.1{STAGE_PREFIX}/api/v1/customer-services",
            check=False,
        )
        run(
            ssh,
            "curl -sk -o /dev/null -w 'stage_api_get:%{http_code}\\n' "
            f"-H 'Host: {HOST}' "
            "-H 'X-Tenant-ID: 00000000-0000-0000-0000-000000000001' "
            f"https://127.0.0.1{STAGE_PREFIX}/api/v1/customer-services/"
            "00000000-0000-0000-0000-000000000101",
            check=False,
        )
        run(
            ssh,
            "curl -s -o /dev/null -w 'prod_list:%{http_code}\\n' "
            "-H 'X-Tenant-ID: 00000000-0000-0000-0000-000000000001' "
            "http://127.0.0.1:8000/api/v1/customer-services",
            check=False,
        )
        run(
            ssh,
            "curl -s -o /dev/null -w 'prod_post:%{http_code}\\n' "
            "-H 'X-Tenant-ID: 00000000-0000-0000-0000-000000000001' "
            "-H 'Content-Type: application/json' "
            "-d '{}' "
            "http://127.0.0.1:8000/api/v1/customer-services",
            check=False,
        )
        run(
            ssh,
            "curl -s -o /dev/null -w 'prod_api_get:%{http_code}\\n' "
            "-H 'X-Tenant-ID: 00000000-0000-0000-0000-000000000001' "
            "http://127.0.0.1:8000/api/v1/customer-services/"
            "00000000-0000-0000-0000-000000000101",
            check=False,
        )
        run(
            ssh,
            "test -d "
            f"{PROD_ROOT}/platform-api/src/yino_platform_api.bak-20260813-113313 "
            f"&& test -d {PROD_ROOT}/frontend-dist.bak-20260813-113342 "
            "&& echo PROD_ROLLBACK_BACKUPS_PRESENT",
            check=False,
        )
    finally:
        tar_path.unlink(missing_ok=True)
        ssh.close()

    print(f"\nPROD (unchanged API :8000): https://{HOST}/#/login")
    print(f"STAGE1 (yinovoice apps): https://{HOST}{STAGE_PREFIX}/#/login")
    print("STAGE1 demo: demo / demo123")
    print(f"STAGE1 assistants: https://{HOST}{STAGE_PREFIX}/#/user/assistant-settings")
    print(f"STAGE1 knowledge: https://{HOST}{STAGE_PREFIX}/#/user/knowledge-base/index")


if __name__ == "__main__":
    main()
