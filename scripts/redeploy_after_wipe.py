#!/usr/bin/env python3
"""Rebuild /opt/yino-vapi from local worktree + /root/deploy-package after wipe.

Upgrades LiveKit server to v1.9.12+ (fixes /rtc/v1 404 with modern livekit-client).
"""
from __future__ import annotations

import os
import sys
import tarfile
import tempfile
from pathlib import Path

import paramiko

HOST = os.environ.get("BT_HOST", "8.215.80.82")
PASSWORD = os.environ.get("BT_PASSWORD", "")
LOCAL_ROOT = Path(__file__).resolve().parents[1]
LOCAL_FRONT = LOCAL_ROOT / "front" / "dist"
LOCAL_PLATFORM = LOCAL_ROOT / "platform-api"
LOCAL_VOICE = LOCAL_ROOT / "voice-agent"
LK_VERSION = "v1.9.12"
LK_TGZ = "livekit_1.9.12_linux_amd64.tar.gz"


def run(ssh: paramiko.SSHClient, cmd: str, check: bool = True, timeout: int = 900) -> str:
    print(f"$ {cmd[:200]}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip()[-4000:])
    if err.strip():
        print(err.rstrip()[-2000:], file=sys.stderr)
    if check and code != 0:
        raise RuntimeError(f"failed ({code}): {cmd[:120]}")
    return out


def pack_src(src: Path, arc_root: str, tar: tarfile.TarFile) -> None:
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        if any(p in {".venv", "__pycache__", ".pytest_cache", "node_modules", "dist"} for p in path.parts):
            continue
        if path.name == ".env.local" or path.suffix == ".pyc":
            continue
        tar.add(path, arcname=f"{arc_root}/{path.relative_to(src).as_posix()}")


def main() -> None:
    if not PASSWORD:
        raise SystemExit("BT_PASSWORD required")
    if not LOCAL_FRONT.is_dir():
        raise SystemExit(f"missing front dist: {LOCAL_FRONT}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting root@{HOST} ...")
    ssh.connect(HOST, username="root", password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tar_path = Path(tmp.name)
    try:
        with tarfile.open(tar_path, "w:gz") as tar:
            pack_src(LOCAL_PLATFORM, "platform-api", tar)
            pack_src(LOCAL_VOICE, "voice-agent", tar)
            for path in LOCAL_FRONT.rglob("*"):
                if path.is_file():
                    tar.add(
                        path,
                        arcname="frontend-dist/" + path.relative_to(LOCAL_FRONT).as_posix(),
                    )
        sftp = ssh.open_sftp()
        remote_tar = "/tmp/yino-redeploy-src.tar.gz"
        print(f"Uploading {tar_path} -> {remote_tar}")
        sftp.put(str(tar_path), remote_tar)
        sftp.close()

        # Refresh deploy-package sources from local worktree.
        run(
            ssh,
            """
set -e
PKG=/root/deploy-package
test -d "$PKG"
rm -rf "$PKG/src/platform-api" "$PKG/src/voice-agent" "$PKG/src/frontend-dist"
mkdir -p "$PKG/src"
tar -xzf /tmp/yino-redeploy-src.tar.gz -C "$PKG/src"
rm -f /tmp/yino-redeploy-src.tar.gz
# Force LiveKit upgrade path in deploy.sh
sed -i 's/LK_VERSION=.*/LK_VERSION=v1.9.12/' "$PKG/deploy.sh"
sed -i 's/LK_TGZ=.*/LK_TGZ="livekit_1.9.12_linux_amd64.tar.gz"/' "$PKG/deploy.sh"
# Always re-download LiveKit binary (wipe left no binary, but be explicit)
rm -f /opt/yino-vapi/bin/livekit-server
echo SRC_REFRESHED
ls -la "$PKG/src"
""",
        )

        # Full redeploy (creates /opt/yino-vapi, venvs, services, nginx).
        run(ssh, "cd /root/deploy-package && bash deploy.sh", timeout=1200)

        # Ensure nginx has longer LiveKit timeouts + stage1 path for side-by-side later.
        run(
            ssh,
            """
set -e
CONF=/www/server/panel/vhost/nginx/yino-vapi-443.conf
test -f "$CONF"
# Point stage1 static (if present) under /stage1/ without separate API stack for now:
# stage1 front currently expects /stage1 API; skip until main works.
nginx -t
nginx -s reload
systemctl is-active yino-livekit yino-platform-api yino-voice-agent
/opt/yino-vapi/bin/livekit-server --version || true
ss -lntp | grep -E ':(443|7880|7881|8000)\\b' || true
curl -sk -o /dev/null -w 'front:%{http_code}\\n' -H 'Host: 8.215.80.82' https://127.0.0.1/
curl -s -o /dev/null -w 'api:%{http_code}\\n' -H 'X-Tenant-ID: 00000000-0000-0000-0000-000000000001' \\
  http://127.0.0.1:8000/api/v1/customer-services/00000000-0000-0000-0000-000000000101
curl -sk -o /dev/null -w 'livekit_rtc:%{http_code}\\n' https://127.0.0.1/livekit/rtc/v1 || true
sleep 3
journalctl -u yino-voice-agent -n 15 --no-pager
""",
        )
    finally:
        tar_path.unlink(missing_ok=True)
        ssh.close()

    print(f"\nOK: https://{HOST}/#/login")
    print("Demo: demo / demo123")
    print("Realtime: https://{HOST}/#/user/realtime-voice")
    print(f"LiveKit target version: {LK_VERSION}")


if __name__ == "__main__":
    main()
