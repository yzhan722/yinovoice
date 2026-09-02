from __future__ import annotations

import pytest

from yino_voice_agent.config import ConfigurationError
from yino_voice_agent.startup import WorkerStartupSettings


def _qwen_env() -> dict[str, str]:
    return {
        "DASHSCOPE_API_KEY": "dashscope-test-key",
        "QWEN_REALTIME_URL": "wss://workspace.example/api-ws/v1/realtime",
    }


def test_synthetic_test_mode_skips_live_credentials() -> None:
    settings = WorkerStartupSettings.from_env({}, mode="synthetic-test")
    assert settings.mode == "synthetic-test"
    assert settings.provider is None
    assert settings.drain_timeout_s == 30.0
    assert settings.ops_host == "127.0.0.1"
    assert settings.sanitized_summary()["livekit_api_secret"] == "missing"


def test_stage_requires_lookup_token_and_livekit_without_leaking_secrets() -> None:
    secret = "super-secret-livekit-value"
    env = _qwen_env() | {
        "VOICE_RUNTIME_MODE": "stage",
        "LIVEKIT_URL": "wss://livekit.example",
        "LIVEKIT_API_KEY": "devkey",
        "LIVEKIT_API_SECRET": secret,
        "PLATFORM_API_URL": "https://platform.example",
    }
    with pytest.raises(ConfigurationError, match="PHONE_LOOKUP_TOKEN missing") as error:
        WorkerStartupSettings.from_env(env)
    assert secret not in str(error.value)


def test_stage_rejects_empty_dispatch_opt_in() -> None:
    env = _qwen_env() | {
        "LIVEKIT_URL": "wss://livekit.example",
        "LIVEKIT_API_KEY": "devkey",
        "LIVEKIT_API_SECRET": "secret",
        "PLATFORM_API_URL": "https://platform.example",
        "PHONE_LOOKUP_TOKEN": "lookup-token",
        "ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV": "true",
    }
    with pytest.raises(
        ConfigurationError, match="ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV"
    ):
        WorkerStartupSettings.from_env(env, mode="stage")


def test_stage_accepts_complete_static_config() -> None:
    settings = WorkerStartupSettings.from_env(
        _qwen_env()
        | {
            "LIVEKIT_URL": "wss://livekit.example",
            "LIVEKIT_API_KEY": "devkey",
            "LIVEKIT_API_SECRET": "secret",
            "PLATFORM_API_URL": "https://platform.example",
            "PHONE_LOOKUP_TOKEN": "lookup-token",
        },
        mode="stage",
    )
    summary = settings.sanitized_summary()
    assert settings.mode == "stage"
    assert summary["phone_lookup_token"] == "configured"
    assert summary["livekit_api_secret"] == "configured"
    assert "secret" not in list(summary.values())
    assert settings.allow_empty_dispatch_metadata_local_dev is False


def test_invalid_drain_timeout_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="VOICE_WORKER_DRAIN_TIMEOUT_SECONDS"):
        WorkerStartupSettings.from_env(
            {"VOICE_WORKER_DRAIN_TIMEOUT_SECONDS": "0"}, mode="synthetic-test"
        )


def test_unknown_runtime_mode_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="VOICE_RUNTIME_MODE"):
        WorkerStartupSettings.from_env({"VOICE_RUNTIME_MODE": "prod"})


def test_ops_host_zero_zero_zero_zero_is_coerced() -> None:
    settings = WorkerStartupSettings.from_env(
        {"VOICE_OPS_HOST": "0.0.0.0"}, mode="synthetic-test"
    )
    assert settings.ops_host == "127.0.0.1"
