#!/usr/bin/env python3
"""Deploy stage1 front dist to Baota nginx on port 38428 (does not touch 17433)."""
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
PORT = int(os.environ.get("BT_HTTP_PORT", "38428"))
REMOTE_DIR = os.environ.get("BT_REMOTE_DIR", "/www/wwwroot/yinovapi-stage1")
SITE_CONF = "/www/server/panel/vhost/nginx/yinovapi-stage1.conf"
LOCAL_DIST = Path(__file__).resolve().parents[1] / "dist"

NGINX_CONF = f"""
server {{
    listen {PORT};
    listen [::]:{PORT};
    server_name _;
    root {REMOTE_DIR};
    index index.html;
    client_max_body_size 200m;

    location /api/v1/ {{
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }}

    location /livekit/ {{
        proxy_pass http://127.0.0.1:7880/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }}
    location = /livekit {{
        return 301 /livekit/;
    }}

    location / {{
        try_files $uri $uri/ /index.html;
    }}

    location ~* \\.(js|css|png|jpg|jpeg|gif|svg|ico|woff2?)$ {{
        expires 7d;
        add_header Cache-Control "public";
        try_files $uri =404;
    }}

    access_log /www/wwwlogs/yinovapi-stage1.access.log;
    error_log  /www/wwwlogs/yinovapi-stage1.error.log;
}}
""".lstrip()


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

    run(ssh, f"mkdir -p {REMOTE_DIR} /www/wwwlogs /www/server/panel/vhost/nginx")

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tar_path = Path(tmp.name)
    try:
        with tarfile.open(tar_path, "w:gz") as tar:
            for path in LOCAL_DIST.rglob("*"):
                if path.is_file():
                    tar.add(path, arcname=path.relative_to(LOCAL_DIST).as_posix())

        sftp = ssh.open_sftp()
        remote_tar = "/tmp/yinovapi-stage1.tar.gz"
        print(f"Uploading {tar_path} -> {remote_tar}")
        sftp.put(str(tar_path), remote_tar)
        with sftp.file("/tmp/yinovapi-stage1.conf", "w") as handle:
            handle.write(NGINX_CONF)
        sftp.close()

        run(
            ssh,
            f"rm -rf {REMOTE_DIR}/* && tar -xzf {remote_tar} -C {REMOTE_DIR} && rm -f {remote_tar}",
        )
        run(ssh, f"cp /tmp/yinovapi-stage1.conf {SITE_CONF} && rm -f /tmp/yinovapi-stage1.conf")
        run(ssh, f"command -v bt && bt 10 {PORT} 2>/dev/null || true", check=False)
        run(
            ssh,
            f"firewall-cmd --permanent --add-port={PORT}/tcp 2>/dev/null; "
            f"firewall-cmd --reload 2>/dev/null || true",
            check=False,
        )
        run(
            ssh,
            f"iptables -C INPUT -p tcp --dport {PORT} -j ACCEPT 2>/dev/null || "
            f"iptables -I INPUT -p tcp --dport {PORT} -j ACCEPT 2>/dev/null || true",
            check=False,
        )

        nginx_bin = "/www/server/nginx/sbin/nginx"
        run(ssh, f"test -x {nginx_bin} && {nginx_bin} -t || nginx -t")
        run(
            ssh,
            f"test -x {nginx_bin} && {nginx_bin} -s reload || "
            "(systemctl reload nginx || service nginx reload)",
        )
        run(ssh, f"ss -lntp | grep ':{PORT}' || true", check=False)
        run(
            ssh,
            f"curl -sI -o /dev/null -w '%{{http_code}}\\n' http://127.0.0.1:{PORT}/",
            check=False,
        )
        run(
            ssh,
            "curl -s -o /dev/null -w '%{http_code}\\n' "
            "-H 'X-Tenant-ID: 00000000-0000-0000-0000-000000000001' "
            f"http://127.0.0.1:{PORT}/api/v1/customer-services/"
            "00000000-0000-0000-0000-000000000101",
            check=False,
        )
    finally:
        tar_path.unlink(missing_ok=True)
        ssh.close()

    print(f"\nOK: http://{HOST}:{PORT}/#/login")
    print("Demo: demo / demo123")
    print(f"Knowledge base: http://{HOST}:{PORT}/#/user/knowledge-base/index")
    print("Note: ensure Alibaba Cloud security group allows TCP", PORT)


if __name__ == "__main__":
    main()
