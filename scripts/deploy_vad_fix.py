#!/usr/bin/env python3
"""Deploy turn-detection / stuck-speech fix to 8.215.80.82."""
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


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 180) -> str:
    print(f"$ {cmd[:160]}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip()[-5000:])
    if err.strip():
        print(err.rstrip()[-2000:], file=sys.stderr)
    if code != 0:
        raise RuntimeError(f"remote failed ({code})")
    return out


def main() -> None:
    if not PASSWORD:
        raise SystemExit("BT_PASSWORD required")
    files = [
        ROOT / "voice-agent/src/yino_voice_agent/qwen_realtime.py",
        ROOT / "voice-agent/src/yino_voice_agent/qwen_realtime_protocol.py",
    ]
    front = ROOT / "front" / "dist"
    for path in files:
        if not path.is_file():
            raise SystemExit(f"missing {path}")
    if not front.is_dir():
        raise SystemExit(f"missing front dist: {front}")

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
            for path in files:
                tar.add(
                    path,
                    arcname=f"voice-agent/src/yino_voice_agent/{path.name}",
                )
            for path in front.rglob("*"):
                if path.is_file():
                    tar.add(
                        path,
                        arcname="frontend-dist/"
                        + path.relative_to(front).as_posix(),
                    )
        sftp = ssh.open_sftp()
        remote = "/tmp/yino-vad-fix.tar.gz"
        print(f"upload {tar_path} -> {remote} ({tar_path.stat().st_size} bytes)")
        sftp.put(str(tar_path), remote)
        sftp.close()

        run(
            ssh,
            r"""
set -euo pipefail
OPT=/opt/yino-vapi
PKG=/root/deploy-package
rm -rf /tmp/yino-vad-unpack
mkdir -p /tmp/yino-vad-unpack
tar -xzf /tmp/yino-vad-fix.tar.gz -C /tmp/yino-vad-unpack
mkdir -p "$PKG/src/voice-agent/src/yino_voice_agent"
cp -f /tmp/yino-vad-unpack/voice-agent/src/yino_voice_agent/qwen_realtime.py \
  "$PKG/src/voice-agent/src/yino_voice_agent/"
cp -f /tmp/yino-vad-unpack/voice-agent/src/yino_voice_agent/qwen_realtime_protocol.py \
  "$PKG/src/voice-agent/src/yino_voice_agent/"
PYDIR="$OPT/voice-agent/src/yino_voice_agent"
echo "INSTALL_DIR=$PYDIR"
test -d "$PYDIR"
cp -f /tmp/yino-vad-unpack/voice-agent/src/yino_voice_agent/qwen_realtime.py "$PYDIR/"
cp -f /tmp/yino-vad-unpack/voice-agent/src/yino_voice_agent/qwen_realtime_protocol.py "$PYDIR/"
rm -rf "$OPT/frontend-dist"
mkdir -p "$OPT/frontend-dist"
cp -a /tmp/yino-vad-unpack/frontend-dist/. "$OPT/frontend-dist/"
rm -rf /tmp/yino-vad-unpack /tmp/yino-vad-fix.tar.gz
systemctl restart yino-voice-agent
sleep 2
systemctl is-active yino-voice-agent yino-platform-api yino-livekit
"$OPT/voice-agent/.venv/bin/python" - <<'PY'
from yino_voice_agent.qwen_realtime_protocol import QwenSessionOptions, build_session_update
from yino_voice_agent import qwen_realtime as qr
ev = build_session_update(QwenSessionOptions(instructions='x', voice='longanqian'))
td = ev['session']['turn_detection']
print(td)
assert td['type'] == 'server_vad'
assert td['threshold'] == 0.35
assert td['silence_duration_ms'] == 450
assert qr.STUCK_SPEECH_SILENCE_S == 1.8
assert qr.INPUT_BARGE_IN_PEAK == 5000
assert qr.BARGE_IN_CONFIRM_S == 0.55
assert hasattr(qr.QwenRealtimeSession, '_force_end_speech_turn')
assert hasattr(qr.QwenRealtimeSession, '_is_recoverable_server_error')
print('smoke_ok')
PY
nginx -s reload || true
curl -sk -o /dev/null -w 'front:%{http_code}\n' -H 'Host: 8.215.80.82' https://127.0.0.1/
""",
            timeout=180,
        )
    finally:
        tar_path.unlink(missing_ok=True)
        ssh.close()
    print("deployed")


if __name__ == "__main__":
    main()
