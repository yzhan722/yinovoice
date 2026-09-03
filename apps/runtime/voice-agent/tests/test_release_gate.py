from __future__ import annotations

from pathlib import Path

from yino_voice_agent.release_gate import run_gate


def test_all_green_is_pass(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []

    def runner(argv: list[str] | tuple[str, ...], cwd: Path) -> int:
        calls.append(tuple(argv))
        _ = cwd
        return 0

    verdict = run_gate(mode="fast", runner=runner, root=tmp_path, python="python")
    assert verdict == "PASS"
    assert calls
    assert any("pytest" in item for step in calls for item in step)


def test_pytest_failure_is_fail(tmp_path: Path) -> None:
    def runner(argv: list[str] | tuple[str, ...], cwd: Path) -> int:
        _ = cwd
        if "pytest" in argv:
            return 2
        return 0

    assert (
        run_gate(mode="fast", runner=runner, root=tmp_path, python="python") == "FAIL"
    )


def test_ruff_failure_is_fail(tmp_path: Path) -> None:
    def runner(argv: list[str] | tuple[str, ...], cwd: Path) -> int:
        _ = cwd
        if "ruff" in argv:
            return 1
        return 0

    assert (
        run_gate(mode="fast", runner=runner, root=tmp_path, python="python") == "FAIL"
    )


def test_stress_failure_is_fail(tmp_path: Path) -> None:
    def runner(argv: list[str] | tuple[str, ...], cwd: Path) -> int:
        _ = cwd
        if any("test_hardening_stress.py" in item for item in argv):
            return 1
        return 0

    assert (
        run_gate(mode="full", runner=runner, root=tmp_path, python="python") == "FAIL"
    )


def test_secret_env_local_fails(tmp_path: Path) -> None:
    (tmp_path / ".env.local").write_text("DASHSCOPE_API_KEY=should-not-scan-value\n")

    def runner(argv: list[str] | tuple[str, ...], cwd: Path) -> int:
        _ = argv, cwd
        return 0

    assert (
        run_gate(mode="fast", runner=runner, root=tmp_path, python="python") == "FAIL"
    )


def test_package_root_is_voice_agent_dir() -> None:
    from yino_voice_agent.release_gate import package_root

    root = package_root()
    assert (root / "pyproject.toml").is_file()
    assert (root / "tests").is_dir()
    assert (root / "src" / "yino_voice_agent" / "release_gate.py").is_file()
