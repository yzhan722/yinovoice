"""Offline DEV-A release gate. No PSTN, no LiveKit mutation, no S3."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

Runner = Callable[[Sequence[str], Path], int]

FORBIDDEN_NAMES = {".env.local", ".env"}
FORBIDDEN_SUFFIXES = {".pem", ".p12", ".key"}
SKIP_DIR_NAMES = {
    ".venv",
    "__pycache__",
    ".ruff_cache",
    ".pytest_cache",
    "node_modules",
}


@dataclass(frozen=True, slots=True)
class GateStep:
    name: str
    argv: tuple[str, ...]


def package_root() -> Path:
    return Path(__file__).resolve().parents[2]


def subprocess_runner(argv: Sequence[str], cwd: Path) -> int:
    completed = subprocess.run(list(argv), cwd=cwd, check=False)
    return completed.returncode


def _walk_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        files.append(path)
    return files


def _tracked_files(root: Path) -> list[Path] | None:
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if top.returncode != 0:
        return None
    repo = Path(top.stdout.strip())
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", str(root.resolve())],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if listed.returncode != 0:
        return None
    files: list[Path] = []
    for raw in listed.stdout.split(b"\0"):
        if not raw:
            continue
        path = repo / raw.decode()
        if path.is_file():
            files.append(path)
    return files


def secret_scan(root: Path) -> list[str]:
    hits: list[str] = []
    candidates = _tracked_files(root)
    if candidates is None:
        candidates = _walk_files(root)
    for path in candidates:
        name = path.name
        if name in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            try:
                hits.append(str(path.resolve().relative_to(root.resolve())))
            except ValueError:
                hits.append(path.name)
    return hits


def steps_for(mode: str, python: str) -> list[GateStep]:
    pytest_cmd = (python, "-m", "pytest", "-q")
    ruff_check = (python, "-m", "ruff", "check", "src", "tests", "scripts")
    ruff_format = (python, "-m", "ruff", "format", "--check", "src", "tests", "scripts")
    startup = (
        python,
        "-c",
        "from yino_voice_agent.startup import WorkerStartupSettings; "
        "WorkerStartupSettings.from_env({'VOICE_RUNTIME_MODE':'synthetic-test'}, "
        "mode='synthetic-test')",
    )
    common = [
        GateStep("startup-static", startup),
        GateStep("pytest", pytest_cmd),
        GateStep("ruff-check", ruff_check),
        GateStep("ruff-format", ruff_format),
    ]
    if mode == "fast":
        return common
    return [
        *common,
        GateStep(
            "races",
            (
                python,
                "-m",
                "pytest",
                "-q",
                "tests/test_hardening_lifecycle.py",
                "tests/test_hardening_worker.py",
                "tests/test_ops_shutdown.py",
            ),
        ),
        GateStep(
            "stress",
            (
                python,
                "-m",
                "pytest",
                "-q",
                "tests/test_hardening_stress.py",
                "tests/test_hardening_concurrency.py",
            ),
        ),
        GateStep(
            "replay",
            (
                python,
                "-m",
                "pytest",
                "-q",
                "tests/test_hardening_replay.py",
                "tests/test_voice_ux_replay.py",
                "tests/test_sip_e2e.py",
            ),
        ),
    ]


def run_gate(
    *,
    mode: str,
    runner: Runner,
    root: Path,
    python: str | None = None,
) -> str:
    if mode not in {"fast", "full"}:
        raise ValueError("mode must be fast or full")
    exe = python or sys.executable
    hits = secret_scan(root)
    if hits:
        print("FAIL")
        print("secret-scan", ",".join(hits))
        return "FAIL"
    for step in steps_for(mode, exe):
        code = runner(step.argv, root)
        if code != 0:
            print("FAIL")
            print(step.name)
            return "FAIL"
    print("PASS")
    print("LIVE_SIP_STATUS=NEEDS_LIVEKIT_PROVISIONING")
    return "PASS"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DEV-A offline release gate")
    parser.add_argument("--mode", choices=("fast", "full"), default="full")
    args = parser.parse_args(list(argv) if argv is not None else None)
    verdict = run_gate(mode=args.mode, runner=subprocess_runner, root=package_root())
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
