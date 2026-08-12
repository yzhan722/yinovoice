#!/usr/bin/env python3
"""Deploy dual-prompt + tts_voice changes to 8.215.80.82."""
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
    print(f"$ {cmd[:180]}")
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
    front = ROOT / "front" / "dist"
    if not front.is_dir():
        raise SystemExit(f"missing front dist: {front}")

    files = [
        (
            ROOT / "platform-api/src/yino_platform_api/domain/customer_service.py",
            "platform-api/src/yino_platform_api/domain/customer_service.py",
        ),
        (
            ROOT / "platform-api/src/yino_platform_api/routes/customer_services.py",
            "platform-api/src/yino_platform_api/routes/customer_services.py",
        ),
        (
            ROOT / "voice-agent/src/yino_voice_agent/customer_service.py",
            "voice-agent/src/yino_voice_agent/customer_service.py",
        ),
        (
            ROOT / "voice-agent/src/yino_voice_agent/runtime_config.py",
            "voice-agent/src/yino_voice_agent/runtime_config.py",
        ),
        (
            ROOT / "voice-agent/src/yino_voice_agent/providers.py",
            "voice-agent/src/yino_voice_agent/providers.py",
        ),
        (
            ROOT / "voice-agent/src/yino_voice_agent/server.py",
            "voice-agent/src/yino_voice_agent/server.py",
        ),
    ]
    for local, _ in files:
        if not local.is_file():
            raise SystemExit(f"missing {local}")

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
            for local, arc in files:
                tar.add(local, arcname=arc)
            for path in front.rglob("*"):
                if path.is_file():
                    tar.add(
                        path,
                        arcname="frontend-dist/"
                        + path.relative_to(front).as_posix(),
                    )
        sftp = ssh.open_sftp()
        remote = "/tmp/yino-voice-prompt-ui.tar.gz"
        print(f"upload {tar_path.stat().st_size} bytes")
        sftp.put(str(tar_path), remote)
        sftp.close()

        run(
            ssh,
            r"""
set -euo pipefail
OPT=/opt/yino-vapi
rm -rf /tmp/yino-vpu
mkdir -p /tmp/yino-vpu
tar -xzf /tmp/yino-voice-prompt-ui.tar.gz -C /tmp/yino-vpu
cp -f /tmp/yino-vpu/platform-api/src/yino_platform_api/domain/customer_service.py \
  "$OPT/platform-api/src/yino_platform_api/domain/"
cp -f /tmp/yino-vpu/platform-api/src/yino_platform_api/routes/customer_services.py \
  "$OPT/platform-api/src/yino_platform_api/routes/"
cp -f /tmp/yino-vpu/voice-agent/src/yino_voice_agent/customer_service.py \
  "$OPT/voice-agent/src/yino_voice_agent/"
cp -f /tmp/yino-vpu/voice-agent/src/yino_voice_agent/runtime_config.py \
  "$OPT/voice-agent/src/yino_voice_agent/"
cp -f /tmp/yino-vpu/voice-agent/src/yino_voice_agent/providers.py \
  "$OPT/voice-agent/src/yino_voice_agent/"
cp -f /tmp/yino-vpu/voice-agent/src/yino_voice_agent/server.py \
  "$OPT/voice-agent/src/yino_voice_agent/"
rm -rf "$OPT/frontend-dist"
mkdir -p "$OPT/frontend-dist"
cp -a /tmp/yino-vpu/frontend-dist/. "$OPT/frontend-dist/"
rm -rf /tmp/yino-vpu /tmp/yino-voice-prompt-ui.tar.gz
systemctl restart yino-platform-api yino-voice-agent
sleep 3
systemctl is-active yino-platform-api yino-voice-agent yino-livekit
curl -sS -H 'X-Tenant-ID: 00000000-0000-0000-0000-000000000001' \
  http://127.0.0.1:8000/api/v1/customer-services/00000000-0000-0000-0000-000000000101 \
  -o /tmp/yino-cs.json
python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path('/tmp/yino-cs.json').read_text(encoding='utf-8'))
assert 'platform_prompt' in data and data['platform_prompt']
assert 'tenant_prompt' in data and data['tenant_prompt']
assert data['voice']['tts_voice'] in {
    'longanqian','longanlingxin','longanlingxi','longanxiaoxin','longanlufeng',
    'longanfengyue','longanyuanfei','longanhuan_v3.6','longjielidou_v3.6',
    'longpaopao_v3.6','longhuohuo_v3.6','longchuanshu_v3.6',
    'loongmary','loongeva_v3.6','loongjohn',
}, data['voice']['tts_voice']
assert data['voice']['tts_voice'] not in {'longxiaoxia','longanwen','longanli'}
assert '症状沟通' in data['platform_prompt']
assert '400-0519-020' in data['tenant_prompt']
print('api_ok', 'tts', data['voice']['tts_voice'], 'pp', len(data['platform_prompt']), 'tp', len(data['tenant_prompt']))
PY
"$OPT/voice-agent/.venv/bin/python" - <<'PY'
from yino_voice_agent.runtime_config import RuntimeVoiceProfile, _tts_voice_or_default
assert _tts_voice_or_default('longxiaoxia') == 'longanqian'
assert _tts_voice_or_default('longanhuan_v3.6') == 'longanhuan_v3.6'
print('agent_import_ok')
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
