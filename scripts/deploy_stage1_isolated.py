#!/usr/bin/env python3
"""Deploy local YinoVoicePlatform as an isolated /stage1 stack on 8.215.80.82.

- Restores production frontend from the pre-overwrite backup
- Installs parallel platform-api (:8011) + voice-agent (agent name stage1)
- Serves frontend at https://HOST/stage1/ (existing 443, no new SG port)
- Does not modify prod :8000 / yino-customer-service worker
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
PROD_FRONT_BACKUP = f"{PROD_ROOT}/frontend-dist.bak-20260805-163837"
STAGE_API_PORT = 8011
STAGE_AGENT_NAME = "yino-customer-service-stage1"
STAGE_PREFIX = "/stage1"

LOCAL_ROOT = Path(__file__).resolve().parents[1]
LOCAL_FRONT_DIST = LOCAL_ROOT / "front" / "dist"
LOCAL_PLATFORM = LOCAL_ROOT / "platform-api"
LOCAL_VOICE = LOCAL_ROOT / "voice-agent"

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

        # Restore production frontend that was overwritten earlier.
        run(
            ssh,
            f"test -d {PROD_FRONT_BACKUP} && "
            f"rm -rf {PROD_ROOT}/frontend-dist/* && "
            f"cp -a {PROD_FRONT_BACKUP}/. {PROD_ROOT}/frontend-dist/ && "
            f"echo PROD_FRONT_RESTORED",
        )

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
        # uv venv has no pip; run uploaded src via PYTHONPATH in systemd units.

        # Env: derive secrets from prod files on the server (values not printed).
        run(
            ssh,
            f"""
python3 - <<'PY'
from pathlib import Path

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
PY
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

        # Ensure nginx 443 includes stage1 locations before location /.
        run(
            ssh,
            f"""
set -e
CONF={REMOTE_NGINX}
SNIP=/tmp/yino-vapi-stage1.nginx.conf
MARKER='# Yino stage1 isolated stack'
if grep -q "$MARKER" "$CONF"; then
  python3 - <<'PY'
from pathlib import Path
conf = Path("{REMOTE_NGINX}")
text = conf.read_text(encoding="utf-8")
start = text.find("# Yino stage1 isolated stack")
if start >= 0:
    # remove previous block until blank line before next location or end marker
    end = text.find("\\n    location ", start + 1)
    if end < 0:
        end = text.find("\\n    access_log", start)
    snippet = Path("/tmp/yino-vapi-stage1.nginx.conf").read_text(encoding="utf-8").rstrip() + "\\n\\n"
    # indent snippet like surrounding locations
    indented = "\\n".join(("    " + line if line.strip() else line) for line in snippet.splitlines()) + "\\n\\n"
    if end > start:
        text = text[:start] + indented + text[end+1:]
    else:
        text = text[:start] + indented
    conf.write_text(text, encoding="utf-8")
print("NGINX_STAGE1_REPLACED")
PY
else
  python3 - <<'PY'
from pathlib import Path
conf = Path("{REMOTE_NGINX}")
text = conf.read_text(encoding="utf-8")
snippet = Path("/tmp/yino-vapi-stage1.nginx.conf").read_text(encoding="utf-8").rstrip() + "\\n\\n"
indented = "\\n".join(("    " + line if line.strip() else line) for line in snippet.splitlines()) + "\\n\\n"
needle = "    # 前端静态"
idx = text.find(needle)
if idx < 0:
    needle = "    location / {{"
    idx = text.find(needle)
if idx < 0:
    raise SystemExit("cannot find insertion point in nginx conf")
text = text[:idx] + indented + text[idx:]
conf.write_text(text, encoding="utf-8")
print("NGINX_STAGE1_INSERTED")
PY
fi
rm -f "$SNIP"
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
            "curl -sk -o /dev/null -w 'stage_api:%{http_code}\\n' "
            f"-H 'Host: {HOST}' "
            "-H 'X-Tenant-ID: 00000000-0000-0000-0000-000000000001' "
            f"https://127.0.0.1{STAGE_PREFIX}/api/v1/customer-services/"
            "00000000-0000-0000-0000-000000000101",
            check=False,
        )
        run(
            ssh,
            "curl -s -o /dev/null -w 'prod_api:%{http_code}\\n' "
            "-H 'X-Tenant-ID: 00000000-0000-0000-0000-000000000001' "
            "http://127.0.0.1:8000/api/v1/customer-services/"
            "00000000-0000-0000-0000-000000000101",
            check=False,
        )
    finally:
        tar_path.unlink(missing_ok=True)
        ssh.close()

    print(f"\nPROD (unchanged API :8000): https://{HOST}/#/login")
    print(f"STAGE1 (local worktree): https://{HOST}{STAGE_PREFIX}/#/login")
    print("STAGE1 demo: demo / demo123")
    print(f"STAGE1 knowledge: https://{HOST}{STAGE_PREFIX}/#/user/knowledge-base/index")


if __name__ == "__main__":
    main()
