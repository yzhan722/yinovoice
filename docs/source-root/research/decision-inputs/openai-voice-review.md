# OpenAI 语音能力复核（截至 2026-07-28）

**范围与证据等级。** 仅使用 OpenAI 官方公开资料；本文是平台选型输入，不是中国大陆可用性或合规结论。项目要求保持 `Transcriber`、`Model`、`Voice` 可独立路由，并须保存逐段延迟、转写、工具审计与可中断播放状态。因此，OpenAI 只能作为可替换的 Provider Adapter，不能绕过 Platform Policy。

## 结论与推荐

**推荐：Demo/首个可运营档位以“模块化 STT → 文本 LLM → TTS”为主，Realtime speech-to-speech 作为受控对照实验，而非唯一运行时。**

原因是模块化路径直接对应 PRD 的三段式配置，可单独替换中文 STT、保存/复核文本、向 LLM 注入版本化 Tenant Knowledge Base、在预约前由平台校验 JSON 与患者确认，并让播放队列由编排层取消。OpenAI 官方也区分：Realtime 适合低延迟现场音频；请求式 Audio API 适合文件、有限请求或无需长连接的语音生成。[Realtime and audio](https://developers.openai.com/api/docs/guides/realtime)

`gpt-realtime-2.1` 适合另建端到端延迟、打断、英文自然度的对照档位：它是语音到语音、支持指令和 tool use 的最新公开 Realtime 型号；低成本候选为 `gpt-realtime-2.1-mini`。两者均走 WebRTC、WebSocket 或 SIP，后两者尤其适合服务端电话媒体链路。Realtime 型号页明确列出 **Function calling 支持、Structured outputs 不支持**，故预约等写操作仍必须在平台外部做 schema/权限/二次确认，不能把模型 tool call 当成执行结果。[`gpt-realtime-2.1`](https://developers.openai.com/api/docs/models/gpt-realtime-2.1)；[`gpt-realtime-2.1-mini`](https://developers.openai.com/api/docs/models/gpt-realtime-2.1-mini)

## 当前可选模型与能力

| 层 | 当前公开选择 | 与本项目的直接含义 |
|---|---|---|
| 流式 STT | `gpt-realtime-whisper`：Realtime transcription session 产生 transcript delta，并允许以延迟/质量取舍配置；官方要求以真实音频、语言、口音和领域词测试。 | 可作为 OpenAI `Transcriber` 对照；不要从公开资料推断江浙口音或 8 kHz 电话质量。[实时转写说明](https://developers.openai.com/api/docs/guides/realtime) |
| 有界/录音 STT | `gpt-4o-transcribe`（较准确）、`gpt-4o-mini-transcribe`（较低成本）；`gpt-4o-transcribe-diarize` 可分说话人，但只在 Transcriptions API，未支持 Realtime API。前两者支持 `prompt`，可加入诊所/术语上下文。 | 适合录音复核、离线评测或分段请求；非电话实时主链路。[语音转文本](https://developers.openai.com/api/docs/guides/speech-to-text)；[`gpt-4o-transcribe`](https://developers.openai.com/api/docs/models/gpt-4o-transcribe) |
| 文本 TTS | TTS 指南仍推荐 `gpt-4o-mini-tts`，支持以 instructions 控制口音、情绪、语调、速度、语气等；Speech API 可用 chunked transfer encoding 流式播放，`wav`/`pcm` 是官方推荐的低延迟格式。`tts-1` 与 `tts-1-hd` 为旧替代，前者更低延迟、后者质量更高。 | 适合保持独立 `Voice` Adapter；必须先消除下方“弃用”文档冲突。[文本转语音](https://developers.openai.com/api/docs/guides/text-to-speech) |
| Realtime S2S | `gpt-realtime-2.1` / `gpt-realtime-2.1-mini`：开放 Realtime 会话，收发音频、文本、模型响应、工具调用与 session 事件；官方建议多数生产语音智能体先设 `reasoning.effort: low`。 | 快速获得低延迟与打断体验，但弱化了独立 STT/TTS 供应商路由与可解释性，且不支持 Structured Outputs。[架构选择](https://developers.openai.com/api/docs/guides/realtime) |
| Audio chat（非首选） | `gpt-audio-1.5` 可在 Chat Completions 同时输入/输出音频。 | 它是请求式 audio-chat，不代替电话主链路的 Realtime 会话；不纳入首轮。[音频与语音](https://developers.openai.com/api/docs/guides/audio) |

## Voice、语言与定制边界

Speech API 的 13 个内置音色为：`alloy`、`ash`、`ballad`、`coral`、`echo`、`fable`、`nova`、`onyx`、`sage`、`shimmer`、`verse`、`marin`、`cedar`；官方建议质量优先时尝试 `marin` 或 `cedar`。但 `tts-1`/`tts-1-hd` 只支持其中 9 个（不含 `ballad`、`verse`、`marin`、`cedar`），Realtime 的音色集合又不同，必须按目标模型/API 查询和实测，不能混用清单；Realtime 已生成一次音频后不能再改本会话 voice，且会话最长 60 分钟。[官方音色表](https://developers.openai.com/api/docs/guides/text-to-speech)；[Realtime 会话生命周期](https://developers.openai.com/api/docs/guides/realtime-conversations)

公开文档支持中文与英语（TTS 以输入文本语言生成，STT 列出 Chinese、English），但同时明确 **voices are optimized for English**。这只证明 `zh-CN`、`en-AU`、`en-US`、`en-GB` 可作为语言/文字测试范围；没有提供澳/美/英特定音色、标准普通话或江浙口音、电话 8 kHz 条件下的质量承诺。因此这四种语言/口音都只能标注“待实测”，尤其中文不要作为 OpenAI Voice 的默认生产结论。[TTS 语言说明](https://developers.openai.com/api/docs/guides/text-to-speech)；[STT 语言说明](https://developers.openai.com/api/docs/guides/speech-to-text)

自定义音色不是 Demo 默认能力：仅向合资格客户开放，需销售开通；创建时必须有声优同意录音和与之匹配的样本录音。首轮只开放有商业授权的内置音色；不允许任意患者/员工声音克隆。[Custom voices](https://developers.openai.com/api/docs/guides/text-to-speech)

## 流式、打断与工具调用

- 模块化：STT 用 Realtime transcription 的 deltas；文本 LLM 用其自身的流式接口；Speech API 的音频可在文件完成前播放。编排层应在新意图/人工接管时停止本地播放、关闭或丢弃未发送音频，并写入“已送达音频”审计状态。
- Realtime：会话保持连接并发送音频、接收模型响应、tool calls 与 session events；电话媒体可选 WebSocket 或 SIP。VAD 开启时，服务会检测用户说话、取消当前响应并开新响应；SIP/WebRTC 会自动截断未播放音频。WebSocket 则须客户端立即停播并发 `conversation.item.truncate`；主动取消可发 `response.cancel`（WebRTC/SIP 还可 `output_audio_buffer.clear`）。这与 PRD 的“已送达/未播内容”审计直接对应。官方说明 Realtime 2.1 改进了静音、噪声及 interruption behavior，但没有替代本项目对附和词、重新提问和预约写入的业务状态机。[Realtime 会话与打断](https://developers.openai.com/api/docs/guides/realtime-conversations)
- 工具：Realtime 支持 Function calling、**不支持 Structured Outputs**；所有 scheduling/handoff 调用继续由 Provider-neutral Scheduling Adapter 做 JSON Schema 验证、tenant/patient 权限核验和患者确认。[模型能力表](https://developers.openai.com/api/docs/models/gpt-realtime-2.1)

## 价格、区域与数据控制（仅已公开事实）

- 公开按 token 计价：`gpt-realtime-2.1` 文本输入/输出为 $4/$24 每百万 token、音频输入/输出为 $32/$64；mini 为文本 $0.60/$2.40、音频 $10/$20。`gpt-4o-transcribe` 为音频输入/输出 $2.50/$10；TTS 型号页列 `gpt-4o-mini-tts` 为文本输入 $0.60、音频输出 $12。实际每通话分钟成本仍需用目标音频与缓存比例测得。[实时模型价格](https://developers.openai.com/api/docs/models/gpt-realtime-2.1)；[转写价格](https://developers.openai.com/api/docs/models/gpt-4o-transcribe)；[TTS 价格](https://developers.openai.com/api/docs/models/gpt-4o-mini-tts)
- API 默认不以输入/输出训练模型；公开资料说明 API 输入输出通常 30 天后移除，合资格端点可申请 ZDR。不要把“默认不训练”误写成“零保留”。[企业隐私](https://openai.com/enterprise-privacy/)
- API data residency 为合资格客户的项目配置。公开表列美国、欧洲可 regional processing；新加坡、澳大利亚等列为存储在区域而非 regional processing，且非美国区域需要经批准的 abuse-monitoring controls 与 ZDR 修订。区域外系统数据、客户自身端用户位置导致的传输等不受该承诺覆盖。[数据控制](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint)
- **没有官方证据证明中国大陆可调用、可低延迟、可签约或在中国大陆处理。** 不作任何该等推断；网络连通、采购资格、数据出境、端点路由与 DPA/ZDR 必须单独验证。

## 风险与 API-key 后的必测项

1. **文档状态冲突（上线阻断）**：TTS 指南称 `gpt-4o-mini-tts`“newest and most reliable”，但当前[全模型目录](https://developers.openai.com/api/docs/models/all)把它标成 **Deprecated**。先用目标组织 key 验证实际可创建请求、可锁定/迁移策略、可用音色与限额；未澄清前不得把它写为长期默认 Voice。
2. 用同一 8 kHz PCM/μ-law 电话语料分别测 `zh-CN`（江浙口音普通话）、`en-AU`、`en-US`、`en-GB`：STT CER/WER、数字/姓名/日期/牙科术语、首个 partial/final、TTS 首包/可懂度/盲听、口音是否符合诊所设置；测试中英切换、背景噪声、静音和重连。
3. 实测取消：用户在 TTS 首包前、播送中、工具等待中打断时，Realtime VAD/interruption 与本地媒体队列的实际事件顺序、停止耗时、是否仍有残余音频；再验证 tool call 在取消后的幂等性和“预约未执行”的审计。
4. 对目标项目实测可用模型/voice ID/并发/速率限制、SIP 或 WebSocket 电话接入、成本、区域域名前缀以及 ZDR/data residency 是否获批。尤其确认 Voice、Realtime 和所用端点是否包含在合同与区域能力范围内。

**决策门槛：** 在上述测试、商业音色授权、区域/保留条款和故障降级均通过前，OpenAI 的所有推荐均为“暂定”。
