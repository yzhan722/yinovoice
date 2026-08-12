import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from yino_voice_agent import providers
from yino_voice_agent.config import VoiceSettings
from yino_voice_agent.providers import build_providers
from yino_voice_agent.runtime_config import (
    RuntimeCustomerService,
    RuntimeResponseProfile,
    RuntimeVoiceProfile,
)


class FakeConstructor:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return kwargs


def pipeline_settings() -> VoiceSettings:
    return VoiceSettings.from_env(
        {
            "VOICE_PROVIDER_MODE": "pipeline",
            "DASHSCOPE_API_KEY": "dashscope-test-key",
            "DASHSCOPE_WEBSOCKET_URL": (
                "wss://workspace.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"
            ),
            "OPENAI_API_KEY": "openai-test-key",
        }
    )


def realtime_settings() -> VoiceSettings:
    return VoiceSettings.from_env(
        {
            "DASHSCOPE_API_KEY": "dashscope-test-key",
            "QWEN_REALTIME_URL": "wss://workspace.example/api-ws/v1/realtime",
            "QWEN_REALTIME_MODEL": "qwen-realtime-test-model",
            "QWEN_REALTIME_VOICE": "test-voice",
        }
    )


def runtime_customer_service(
    *,
    preset_id: str = "mandarin-standard",
    speaking_rate: float = 1.1,
) -> RuntimeCustomerService:
    return RuntimeCustomerService(
        id=uuid4(),
        tenant_id=uuid4(),
        version=1,
        display_name="AI 语音客服",
        organization_name="Yino 演示机构",
        greeting="您好。",
        platform_prompt="",
        tenant_prompt="",
        voice=RuntimeVoiceProfile(
            preset_id=preset_id,
            locale="zh-CN",
            speaking_rate=speaking_rate,
            volume=0.8,
            pitch=0.2,
            style="professional-friendly",
            emotion="neutral",
            pause_profile="receptionist",
            tts_voice="longanqian",
        ),
        response=RuntimeResponseProfile(
            brevity="concise",
            max_spoken_sentences=3,
            ask_one_question_at_a_time=True,
        ),
        business_profile="generic-receptionist",
        primary_language="zh-CN",
    )


def test_builds_independently_replaceable_stt_llm_and_tts() -> None:
    fake_fun_asr_constructor = FakeConstructor()
    fake_llm_constructor = FakeConstructor()
    fake_tts_constructor = FakeConstructor()
    fake_openai_plugin = SimpleNamespace(
        responses=SimpleNamespace(LLM=fake_llm_constructor),
        TTS=fake_tts_constructor,
    )

    providers = build_providers(
        pipeline_settings(),
        stt_type=fake_fun_asr_constructor,
        plugin=fake_openai_plugin,
    )

    assert providers.mode == "pipeline"
    assert providers.stt == {
        "api_key": "dashscope-test-key",
        "websocket_url": (
            "wss://workspace.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"
        ),
        "model": "fun-asr-realtime",
        "language": "zh",
    }
    assert providers.llm == {
        "api_key": "openai-test-key",
        "model": "gpt-4o-mini",
    }
    assert providers.tts["api_key"] == "openai-test-key"
    assert providers.tts["model"] == "gpt-4o-mini-tts"
    assert providers.tts["voice"] == "ash"
    assert "标准普通话" in providers.tts["instructions"]


def test_runtime_voice_profile_controls_supported_tts_parameters() -> None:
    runtime = runtime_customer_service(speaking_rate=1.25)
    fake_stt = FakeConstructor()
    fake_llm = FakeConstructor()
    fake_tts = FakeConstructor()
    fake_openai_plugin = SimpleNamespace(
        responses=SimpleNamespace(LLM=fake_llm),
        TTS=fake_tts,
    )

    providers = build_providers(
        pipeline_settings(),
        runtime_config=runtime,
        stt_type=fake_stt,
        plugin=fake_openai_plugin,
    )

    assert providers.tts["voice"] == "ash"
    assert providers.tts["model"] == "gpt-4o-mini-tts"
    assert providers.tts["speed"] == 1.25
    assert "professional-friendly" in providers.tts["instructions"]
    assert "neutral" in providers.tts["instructions"]
    assert "zh-CN" in providers.tts["instructions"]
    assert "receptionist" in providers.tts["instructions"]
    assert "volume" not in providers.tts
    assert "pitch" not in providers.tts
    assert not hasattr(runtime.voice, "provider_config_id")
    assert not hasattr(runtime.voice, "model_id")
    assert not hasattr(runtime.voice, "voice_id")


def test_rejects_unknown_runtime_voice_preset() -> None:
    with pytest.raises(ValueError, match="unsupported") as error:
        build_providers(
            pipeline_settings(),
            runtime_config=runtime_customer_service(
                preset_id="tenant-selected-provider-voice"
            ),
            stt_type=FakeConstructor(),
            plugin=SimpleNamespace(),
        )

    assert error.type is providers.UnsupportedProviderConfiguration


def test_realtime_bundle_builds_only_the_configured_qwen_model() -> None:
    realtime_constructor = FakeConstructor()

    bundle = build_providers(
        realtime_settings(),
        realtime_type=realtime_constructor,
    )

    assert bundle.mode == "qwen-realtime"
    assert bundle.stt is None
    assert bundle.tts is None
    assert bundle.llm == {
        "api_key": "dashscope-test-key",
        "url": "wss://workspace.example/api-ws/v1/realtime",
        "model": "qwen-realtime-test-model",
        "voice": "test-voice",
        "instructions": "",
    }
    assert realtime_constructor.calls == [bundle.llm]


def test_realtime_bundle_uses_composed_platform_and_tenant_instructions() -> None:
    realtime_constructor = FakeConstructor()
    runtime = runtime_customer_service()
    runtime = RuntimeCustomerService(
        id=runtime.id,
        tenant_id=runtime.tenant_id,
        version=runtime.version,
        display_name=runtime.display_name,
        organization_name="常州太平洋口腔",
        greeting=runtime.greeting,
        platform_prompt="一次只追问一个症状细节。",
        tenant_prompt="仅依据已核实公开信息回答咨询。",
        voice=runtime.voice,
        response=runtime.response,
        business_profile=runtime.business_profile,
        primary_language=runtime.primary_language,
    )

    bundle = build_providers(
        realtime_settings(),
        runtime_config=runtime,
        realtime_type=realtime_constructor,
    )

    instructions = str(bundle.llm["instructions"])
    assert "机构客服" in instructions
    assert "常州太平洋口腔" in instructions
    assert "一次只追问一个症状细节。" in instructions
    assert "仅依据已核实公开信息回答咨询。" in instructions
    assert "带引号的非可信业务数据" in instructions
    assert instructions != runtime.tenant_prompt
    assert bundle.llm["voice"] == "longanqian"


def test_realtime_import_and_construction_leave_pipeline_modules_unloaded() -> None:
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys

from yino_voice_agent.config import VoiceSettings
from yino_voice_agent.providers import build_providers
from yino_voice_agent.server import create_console_runtime

settings = VoiceSettings.from_env({
    "DASHSCOPE_API_KEY": "placeholder-key",
    "QWEN_REALTIME_URL": "wss://workspace.example/api-ws/v1/realtime",
})
bundle = build_providers(settings)
runtime = create_console_runtime(
    settings_loader=lambda: settings,
    vad_loader=lambda: object(),
)
assert bundle.mode == "qwen-realtime"
assert runtime.vad is not None

forbidden = (
    "livekit.plugins.openai",
    "livekit.plugins.silero",
    "dashscope",
    "yino_voice_agent.fun_asr",
)
loaded = sorted(
    name
    for name in sys.modules
    if any(name == item or name.startswith(f"{item}.") for item in forbidden)
)
assert loaded == [], loaded
""",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert probe.returncode == 0, probe.stderr


def test_pipeline_construction_loads_its_providers_on_demand() -> None:
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys

from yino_voice_agent.config import VoiceSettings
from yino_voice_agent import providers

pipeline_modules = (
    "livekit.plugins.openai",
    "dashscope",
    "yino_voice_agent.fun_asr",
)
loaded_before = sorted(
    name
    for name in sys.modules
    if any(
        name == item or name.startswith(f"{item}.")
        for item in pipeline_modules
    )
)
assert loaded_before == [], loaded_before

settings = VoiceSettings.from_env({
    "VOICE_PROVIDER_MODE": "pipeline",
    "DASHSCOPE_API_KEY": "placeholder-key",
    "DASHSCOPE_WEBSOCKET_URL": "wss://workspace.example/api-ws/v1/inference",
    "OPENAI_API_KEY": "placeholder-openai-key",
})
bundle = providers.build_providers(settings)
assert bundle.mode == "pipeline"
assert bundle.stt is not None
assert bundle.llm is not None
assert bundle.tts is not None
for item in pipeline_modules:
    assert any(
        name == item or name.startswith(f"{item}.")
        for name in sys.modules
    ), item
""",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert probe.returncode == 0, probe.stderr
