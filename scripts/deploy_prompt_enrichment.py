#!/usr/bin/env python3
"""Deploy enriched Pacific demo prompt to 8.215.80.82."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

HOST = os.environ.get("BT_HOST", "8.215.80.82")
PASSWORD = os.environ.get("BT_PASSWORD", "")
ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "platform-api/src/yino_platform_api/domain/customer_service.py"
REMOTE = "/opt/yino-vapi/platform-api/src/yino_platform_api/domain/customer_service.py"
PKG = "/root/deploy-package/src/platform-api/src/yino_platform_api/domain/customer_service.py"


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 120) -> str:
    print(f"$ {cmd[:160]}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip()[-4000:])
    if err.strip():
        print(err.rstrip()[-1500:], file=sys.stderr)
    if code != 0:
        raise RuntimeError(f"remote failed ({code})")
    return out


def main() -> None:
    if not PASSWORD:
        raise SystemExit("BT_PASSWORD required")
    if not LOCAL.is_file():
        raise SystemExit(f"missing {LOCAL}")

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
    try:
        sftp = ssh.open_sftp()
        print(f"upload {LOCAL} -> {REMOTE}")
        sftp.put(str(LOCAL), REMOTE)
        # keep deploy-package copy in sync when present
        try:
            sftp.stat(str(Path(PKG).parent))
            sftp.put(str(LOCAL), PKG)
            print(f"also updated {PKG}")
        except OSError:
            print("deploy-package path skipped")
        sftp.close()

        run(
            ssh,
            r"""
set -euo pipefail
OPT=/opt/yino-vapi
grep -q '项目怎么做' "$OPT/platform-api/src/yino_platform_api/domain/customer_service.py"
grep -q 'brevity="balanced"' "$OPT/platform-api/src/yino_platform_api/domain/customer_service.py"
systemctl restart yino-platform-api
sleep 2
systemctl is-active yino-platform-api yino-voice-agent
# memory repo reseeds demo prompt on restart
curl -sS -H 'X-Tenant-ID: 00000000-0000-0000-0000-000000000001' \
  http://127.0.0.1:8000/api/v1/customer-services/00000000-0000-0000-0000-000000000101 \
  -o /tmp/yino-cs.json
python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path('/tmp/yino-cs.json').read_text(encoding='utf-8'))
prompt = data.get('tenant_prompt', '')
resp = data.get('response', {})
print('prompt_chars', len(prompt))
print('brevity', resp.get('brevity'))
print('max_spoken_sentences', resp.get('max_spoken_sentences'))
assert '项目怎么做' in prompt
assert '种植牙' in prompt
assert '少用' in prompt and '医生检查' in prompt
assert '刺痛' in prompt or '酸痛' in prompt
assert resp.get('brevity') == 'balanced'
assert resp.get('max_spoken_sentences') == 4
print('api_ok')
PY
""",
            timeout=120,
        )
    finally:
        ssh.close()
    print("deployed")


if __name__ == "__main__":
    main()
