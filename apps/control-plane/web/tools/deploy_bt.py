#!/usr/bin/env python3
"""Deploy admin dist to Baota host on an uncommon port."""
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
SSH_PORT = int(os.environ.get("BT_SSH_PORT", "22"))
PORT = int(os.environ.get("BT_HTTP_PORT", "38427"))
REMOTE_DIR = os.environ.get("BT_REMOTE_DIR", "/www/wwwroot/yinovapi-demo")
SITE_CONF = f"/www/server/panel/vhost/nginx/yinovapi-demo.conf"
LOCAL_DIST = Path(__file__).resolve().parents[1] / "dist"


def run(ssh: paramiko.SSHClient, cmd: str, check: bool = True) -> str:
    print(f"$ {cmd}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=120)
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

    nginx_conf = f"""
server {{
    listen {PORT};
    listen [::]:{PORT};
    server_name _;
    root {REMOTE_DIR};
    index index.html;

    # SPA / Vite hash assets
    location / {{
        try_files $uri $uri/ /index.html;
    }}

    location ~* \\.(js|css|png|jpg|jpeg|gif|svg|ico|woff2?)$ {{
        expires 7d;
        add_header Cache-Control "public";
        try_files $uri =404;
    }}

    access_log /www/wwwlogs/yinovapi-demo.access.log;
    error_log  /www/wwwlogs/yinovapi-demo.error.log;
}}
""".lstrip()

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting {USER}@{HOST}:{SSH_PORT} ...")
    ssh.connect(
        HOST,
        port=SSH_PORT,
        username=USER,
        password=PASSWORD,
        timeout=30,
        banner_timeout=60,
        auth_timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )

    # Probe baota / nginx
    run(ssh, "command -v nginx; ls /www/server/nginx/sbin/nginx 2>/dev/null; ls /www/server/panel 2>/dev/null | head", check=False)
    run(ssh, f"mkdir -p {REMOTE_DIR} /www/wwwlogs /www/server/panel/vhost/nginx", check=False)

    # Pack and upload
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tar_path = Path(tmp.name)
    try:
        with tarfile.open(tar_path, "w:gz") as tar:
            for p in LOCAL_DIST.rglob("*"):
                if p.is_file():
                    tar.add(p, arcname=p.relative_to(LOCAL_DIST).as_posix())
        sftp = ssh.open_sftp()
        remote_tar = "/tmp/yinovapi-demo.tar.gz"
        print(f"Uploading {tar_path} -> {remote_tar}")
        sftp.put(str(tar_path), remote_tar)
        conf_remote = "/tmp/yinovapi-demo.conf"
        with sftp.file(conf_remote, "w") as f:
            f.write(nginx_conf)
        sftp.close()

        run(ssh, f"rm -rf {REMOTE_DIR}/* && tar -xzf {remote_tar} -C {REMOTE_DIR} && rm -f {remote_tar}")
        run(ssh, f"cp {conf_remote} {SITE_CONF} && rm -f {conf_remote}")
        # Also drop a copy under conf/include if panel path missing
        run(ssh, f"test -f {SITE_CONF} || cp /dev/null {SITE_CONF}", check=False)

        # Open firewall (firewalld / ufw / iptables / bt)
        run(ssh, f"command -v bt && bt 10 {PORT} 2>/dev/null || true", check=False)
        run(ssh, f"firewall-cmd --permanent --add-port={PORT}/tcp 2>/dev/null; firewall-cmd --reload 2>/dev/null || true", check=False)
        run(ssh, f"ufw allow {PORT}/tcp 2>/dev/null || true", check=False)
        run(ssh, f"iptables -I INPUT -p tcp --dport {PORT} -j ACCEPT 2>/dev/null || true", check=False)
        # Alibaba cloud often needs security group; we still try local firewall

        # Test nginx and reload
        nginx_bin = "/www/server/nginx/sbin/nginx"
        run(ssh, f"test -x {nginx_bin} && {nginx_bin} -t || nginx -t")
        run(ssh, f"test -x {nginx_bin} && {nginx_bin} -s reload || (systemctl reload nginx || service nginx reload)")
        run(ssh, f"ss -lntp | grep ':{PORT}' || netstat -lntp 2>/dev/null | grep ':{PORT}'", check=False)
        run(ssh, f"curl -sI -o /dev/null -w '%{{http_code}}\\n' http://127.0.0.1:{PORT}/", check=False)
    finally:
        tar_path.unlink(missing_ok=True)
        ssh.close()

    print(f"\nOK: http://{HOST}:{PORT}/#/login")
    print("Demo: demo / demo123")


if __name__ == "__main__":
    main()
