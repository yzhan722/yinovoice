# Vapi 三层（STT / LLM / TTS）复刻可行性

日期：2026-09-06  
调研对象：Vapi 账户 15 个助手（旧管理台 MySQL 存有 13 个的完整三层 JSON，比 Vapi 列表接口更细）  
结论：**13 个助手中 10 个可 1:1 复刻**（同供应商、同模型、同音色 ID、同调参）；**3 个用 Vapi 自有音色的需要替换音色**。

> 本文不含客户名称、号码与提示词内容。助手名仅为技术标识。

## 1. 现状三层配置

| 层 | Vapi 在用 | 数量 |
|---|---|---|
| STT | `deepgram/nova-2`（en） | 4 |
| | `deepgram/flux-general-en`（en） | 4 |
| | `deepgram/nova-3`（en） | 2 |
| | `openai/gpt-4o-transcribe`（zh） | 2 |
| | `deepgram/nova-2`（zh） | 1 |
| LLM | `openai/gpt-4o` | 12 |
| | `openai/gpt-4.1` | 1 |
| TTS | `11labs/eleven_turbo_v2_5` | 7 |
| | `11labs/eleven_flash_v2_5` | 3 |
| | `vapi/*`（Layla / Emma / Nico 自有音色） | 3 |

TTS 调参使用情况：`stability` 10 个、`similarityBoost` 10 个、`speed` 2 个、`style` 2 个。  
LLM 侧另有 `maxTokens`（7 个）、`temperature`（7 个）、`toolIds`（9 个）、`knowledgeBase`（1 个）。

## 2. 逐项复刻结论

| 项 | LiveKit 侧 | 结论 |
|---|---|---|
| Deepgram nova-2 / nova-3 | `livekit-plugins-deepgram` 的 `STT(model=...)`，`DeepgramModels` 含 `nova-2-*` 与 `nova-3` | **完全一致**。另有 `nova-2-phonecall` / `nova-2-conversationalai` 专为电话音频优化，是可选升级 |
| Deepgram flux-general-en | 同插件的 **`STTv2`**（`V2Models` 含 `flux-general-en`），参数用 `language_hint` | **完全一致**，但客户端类不同，代码已按模型名自动选择 |
| OpenAI gpt-4o-transcribe | `livekit-plugins-openai` 的 `STT`，`STTModels` 含 `gpt-4o-transcribe` | **完全一致** |
| GPT-4o / GPT-4.1 | 已有 OpenAI 插件；`LLM_PROVIDER` 注册表还可换 DeepSeek / Qwen / GLM 等 | **完全一致** |
| ElevenLabs eleven_turbo_v2_5 / eleven_flash_v2_5 | `livekit-plugins-elevenlabs` 的 `TTS(model=..., voice_id=...)`，`TTSModels` 两者都在 | **完全一致，音色 ID 可直接复用**（同一供应商账户） |
| ElevenLabs 调参 | `VoiceSettings(stability, similarity_boost, style, speed, use_speaker_boost)` | **完全一致**，正好覆盖 Vapi 用到的四个 |
| Vapi 自有音色（Layla / Emma / Nico） | 无对应物，属 Vapi 专有 | **需替换**：建议用 ElevenLabs 或 Cartesia 试听挑选，切流前请客户确认 |
| `maxTokens` / `temperature` | LiveKit LLM 客户端支持 | 可传，尚未接入实例配置（见待办） |
| `toolIds` | Yino 工具体系不同（`check_availability` / `create_appointment` / `create_callback`） | **需重建**，非参数映射；真人转接见计划 P3.1 |
| `knowledgeBase` | 仅 1 个演示助手在用，且 Vapi 上 3 个文件处理失败 | 忽略 |

## 3. 已落地的能力

`apps/runtime/voice-agent` 新增三张供应商注册表，pipeline 模式的三层都可换供应商，且**不配置任何 `*_PROVIDER` 时行为与原先完全一致**：

- `llm_providers.py`：OpenAI / DeepSeek / Qwen(DashScope 兼容) / Zhipu GLM / Moonshot Kimi / MiniMax / SiliconFlow / OpenRouter / 自建
- `stt_providers.py`：Fun-ASR（默认）/ Deepgram（含 Flux 自动走 v2 客户端）/ OpenAI transcribe
- `tts_providers.py`：OpenAI（默认）/ ElevenLabs（含四项调参）/ Cartesia / CosyVoice（走 qwen-realtime）

环境变量：`{LLM,STT,TTS}_PROVIDER` 选型，`*_MODEL` / `*_BASE_URL` / `*_API_KEY` 覆盖默认，各供应商也读自己的 key 变量以便并存。空值一律报错而非静默回退。

海外供应商插件放在 `overseas` extra，默认安装与 CI 不变：

```bash
pip install -e ".[dev,overseas]"    # 需要 Deepgram / ElevenLabs / Cartesia 时
```

## 4. 迁移一个海外助手的配置对照

以 `deepgram/nova-2 + gpt-4o + 11labs/eleven_turbo_v2_5(stability .5, similarityBoost .75)` 为例：

```bash
VOICE_PROVIDER_MODE=pipeline
AGENT_LANGUAGE=en

STT_PROVIDER=deepgram
STT_MODEL=nova-2-phonecall        # 或 nova-2 保持完全一致
DEEPGRAM_API_KEY=...

LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=...

TTS_PROVIDER=elevenlabs
TTS_MODEL=eleven_turbo_v2_5
TTS_VOICE=<原 Vapi voiceId，直接复用>
TTS_STABILITY=0.5
TTS_SIMILARITY_BOOST=0.75
ELEVENLABS_API_KEY=...
```

## 5. 待办与限制

- **三层配置目前是进程级环境变量，不是实例级**。多个海外助手若需不同三层组合，需按计划 P3.2 引入实例 `runtime_profile`（每档位一个 worker 池），或每租户一个 worker。
- Vapi 自有音色的 3 个助手需人工挑选替代音色并请客户确认。
- `temperature` / `maxTokens` 尚未接入实例配置。
- 本文只证明**配置可复刻**；语音质量与延迟仍需按计划 P3.2 做盲测（雅加达出海线路下的实测）。
- Deepgram / ElevenLabs 需自备账户与配额；两家在雅加达的连通性尚未实测。
