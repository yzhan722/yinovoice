"""Synthetic commercial MVP smoke (in-memory Control Plane API).

Does not call LiveKit, SMTP, S3, or any production host.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "control-plane" / "api"
VENV_PYTHON = API_ROOT / ".venv" / "Scripts" / "python.exe"


def main() -> int:
    python = str(VENV_PYTHON if VENV_PYTHON.exists() else sys.executable)
    completed = subprocess.run(
        [
            python,
            "-m",
            "pytest",
            "tests/test_commercial_mvp_smoke.py",
            "-q",
        ],
        cwd=API_ROOT,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
