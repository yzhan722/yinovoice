#!/usr/bin/env python3
"""Upload front/dist to /opt/yino-vapi/frontend-dist on the demo host."""
from __future__ import annotations

import os
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import paramiko

HOST = os.environ.get("BT_HOST", "8.215.80.82")
USER = os.environ.get("BT_USER", "root")
PASSWORD = os.environ.get("BT_PASSWORD", "")
REMOTE_DIR = os.environ.get("BT_REMOTE_DIR", "/opt/yino-vapi/frontend-dist")
LOCAL_DIST = Path(__file__).resolve().parents[1] / "dist"


def run(ssh: paramiko.SSHClient, cmd: str, check: bool = True) -> str:
    print(f"$ {cmd}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=180)
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


def main() -> None:
    if not PASSWORD:
        raise SystemExit("BT_PASSWORD is required")
    if not LOCAL_DIST.is_dir():
        raise SystemExit(f"dist not found: {LOCAL_DIST}")

    stamp = time.strftime("%Y%m%d-%H%M%S")
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
            for p in LOCAL_DIST.rglob("*"):
                if p.is_file():
                    tar.add(p, arcname=p.relative_to(LOCAL_DIST).as_posix())

        remote_tar = f"/tmp/yinovapi-frontend-{stamp}.tar.gz"
        sftp = ssh.open_sftp()
        print(f"Uploading {tar_path} -> {remote_tar}")
        sftp.put(str(tar_path), remote_tar)
        sftp.close()

        backup = f"{REMOTE_DIR}.bak-{stamp}"
        run(ssh, f"test -d {REMOTE_DIR}")
        run(ssh, f"cp -a {REMOTE_DIR} {backup}")
        run(ssh, f"rm -rf {REMOTE_DIR}/*")
        run(ssh, f"tar -xzf {remote_tar} -C {REMOTE_DIR} && rm -f {remote_tar}")
        run(ssh, f"chown -R root:root {REMOTE_DIR}")
        run(ssh, f"ls -la {REMOTE_DIR} | head -20")
        run(
            ssh,
            "curl -skI -o /dev/null -w '%{http_code}\\n' "
            "-H 'Host: 8.215.80.82' https://127.0.0.1/",
            check=False,
        )
        run(
            ssh,
            "curl -sk -o /dev/null -w '%{http_code}\\n' "
            "-H 'Host: 8.215.80.82' https://127.0.0.1/api/v1/health || "
            "curl -sk -o /dev/null -w '%{http_code}\\n' "
            "-H 'Host: 8.215.80.82' https://127.0.0.1/api/v1/customer-services "
            "-H 'X-Tenant-Id: 00000000-0000-0000-0000-000000000001' || true",
            check=False,
        )
    finally:
        tar_path.unlink(missing_ok=True)
        ssh.close()

    print(f"\nOK: https://{HOST}/")
    print(f"Backup: {REMOTE_DIR}.bak-{stamp}")


if __name__ == "__main__":
    main()
