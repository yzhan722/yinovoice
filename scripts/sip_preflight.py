"""Read-only SIP preflight launcher. Never mutates LiveKit trunks or rules."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "apps" / "runtime" / "voice-agent" / "src"
sys.path.insert(0, str(SRC))

from yino_voice_agent.telephony.preflight import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
