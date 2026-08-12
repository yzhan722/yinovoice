#!/usr/bin/env python3
import os
import sys

import paramiko

HOST = os.environ.get("BT_HOST", "8.215.80.82")
PASSWORD = os.environ.get("BT_PASSWORD", "")

CMD = r"""
set -e
APP=/opt/yino-vapi
LK_VERSION=v1.13.5
LK_TGZ=livekit_1.13.5_linux_amd64.tar.gz
tmpdir=$(mktemp -d)
echo "Downloading $LK_VERSION ..."
curl -fL --retry 3 "https://github.com/livekit/livekit/releases/download/$LK_VERSION/$LK_TGZ" -o "$tmpdir/livekit.tgz"
tar -xzf "$tmpdir/livekit.tgz" -C "$tmpdir"
systemctl stop yino-voice-agent yino-livekit
install -m 755 "$(find "$tmpdir" -type f -name livekit-server | head -1)" "$APP/bin/livekit-server"
rm -rf "$tmpdir"
"$APP/bin/livekit-server" --version
systemctl start yino-livekit
sleep 2
systemctl start yino-voice-agent
sleep 3
systemctl is-active yino-livekit yino-platform-api yino-voice-agent
journalctl -u yino-voice-agent -n 12 --no-pager
"""


def main() -> None:
    if not PASSWORD:
        raise SystemExit("BT_PASSWORD required")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username="root", password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    _, stdout, stderr = ssh.exec_command(CMD, timeout=300)
    sys.stdout.write(stdout.read().decode("utf-8", "replace"))
    err = stderr.read().decode("utf-8", "replace")
    if err.strip():
        sys.stderr.write(err)
    code = stdout.channel.recv_exit_status()
    ssh.close()
    raise SystemExit(code)


if __name__ == "__main__":
    main()
