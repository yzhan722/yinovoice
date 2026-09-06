"""LLM provider registry for pipeline mode.

Every provider here speaks the OpenAI chat-completions protocol, so one
base_url / api_key / model triple covers all of them and the runtime keeps a
single code path. Speech-to-speech models (Qwen Realtime) are not in this
registry: they replace the whole pipeline rather than just the LLM step.

Selection order for each field:
    LLM_MODEL / LLM_BASE_URL / LLM_API_KEY   explicit override
    provider defaults                        from the table below
    provider key env (e.g. DEEPSEEK_API_KEY) so several can coexist
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class LlmProvider:
    key: str
    label: str
    base_url: str | None
    default_model: str
    api_key_envs: tuple[str, ...]
    notes: str = ""


# base_url None means "the plugin default" (OpenAI's own endpoint).
PROVIDERS: Final[dict[str, LlmProvider]] = {
    "openai": LlmProvider(
        key="openai",
        label="OpenAI",
        base_url=None,
        default_model="gpt-4o-mini",
        api_key_envs=("OPENAI_API_KEY",),
    ),
    "deepseek": LlmProvider(
        key="deepseek",
        label="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        api_key_envs=("DEEPSEEK_API_KEY", "OPENAI_API_KEY"),
        notes="Strong Chinese reasoning at low cost; no audio models.",
    ),
    "dashscope": LlmProvider(
        key="dashscope",
        label="Qwen (DashScope compatible mode)",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen-plus",
        api_key_envs=("DASHSCOPE_API_KEY", "OPENAI_API_KEY"),
        notes="Same key as Qwen Realtime; keeps text and voice on one vendor.",
    ),
    "zhipu": LlmProvider(
        key="zhipu",
        label="Zhipu GLM",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-4-plus",
        api_key_envs=("ZHIPU_API_KEY", "GLM_API_KEY", "OPENAI_API_KEY"),
    ),
    "moonshot": LlmProvider(
        key="moonshot",
        label="Moonshot Kimi",
        base_url="https://api.moonshot.cn/v1",
        default_model="moonshot-v1-8k",
        api_key_envs=("MOONSHOT_API_KEY", "KIMI_API_KEY", "OPENAI_API_KEY"),
    ),
    "minimax": LlmProvider(
        key="minimax",
        label="MiniMax",
        base_url="https://api.minimax.chat/v1",
        default_model="abab6.5s-chat",
        api_key_envs=("MINIMAX_API_KEY", "OPENAI_API_KEY"),
    ),
    "siliconflow": LlmProvider(
        key="siliconflow",
        label="SiliconFlow",
        base_url="https://api.siliconflow.cn/v1",
        default_model="Qwen/Qwen2.5-7B-Instruct",
        api_key_envs=("SILICONFLOW_API_KEY", "OPENAI_API_KEY"),
        notes="Aggregator; model ids are namespaced by publisher.",
    ),
    "openrouter": LlmProvider(
        key="openrouter",
        label="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        default_model="openai/gpt-4o-mini",
        api_key_envs=("OPENROUTER_API_KEY", "OPENAI_API_KEY"),
        notes="Aggregator; useful for A/B testing without new accounts.",
    ),
    "custom": LlmProvider(
        key="custom",
        label="Custom OpenAI-compatible endpoint",
        base_url=None,
        default_model="",
        api_key_envs=("LLM_API_KEY", "OPENAI_API_KEY"),
        notes="Requires LLM_BASE_URL and LLM_MODEL; for self-hosted vLLM etc.",
    ),
}

PROVIDER_KEYS: Final[tuple[str, ...]] = tuple(PROVIDERS)


@dataclass(frozen=True, slots=True)
class LlmSelection:
    """A fully resolved LLM choice, ready to build a plugin client."""

    provider: str
    model: str
    base_url: str | None
    api_key: str

    @property
    def label(self) -> str:
        return PROVIDERS[self.provider].label
