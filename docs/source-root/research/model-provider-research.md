# 商业模型供应商调研：Transcriber / Model / Voice

> 版本：v1.1（2026-07-29）
> 场景：中国大陆牙科诊所；江浙口音普通话为中文重点；8 kHz 电话音频；应用、存储和模型处理固定在中国大陆。`en-AU`、`en-US`、`en-GB` 作为大陆候选模型的次级扩展测试，境外供应商留到未来海外 Regional Cell。
> 证据边界：仅采用供应商官方文档、区域/安全资料。本文没有跨供应商、同语料、同电话链路的基准，因此**不声称任何厂商准确率最高**。

> 区域决定：境外模型资料仅作未来国际版本背景，不进入当前大陆 Demo 的运行时白名单。供应商名称来自中国不等于数据处理一定在大陆；仍需核对具体端点、控制台、合同、保留方式和故障转移路径。

## 1. 结论摘要

Demo 建议优先验证三套大陆候选组合，诊所只选择“中文高质量 / 低延迟 / 低成本”等业务档位：

| 档位 | Transcriber（STT） | Model（LLM） | Voice（TTS + 音色） | 结论性质 |
|---|---|---|---|---|
| 大陆候选 A | 阿里云北京端点 `fun-asr-realtime` / `fun-asr-flash-8k-realtime` | 阿里云北京端点 Qwen，具体快照在开通账户后冻结 | 阿里云北京端点 Qwen-TTS 或 CosyVoice 预设音色 | **首选基线**；必须用江浙真人电话集实测 |
| 大陆候选 B | 腾讯云实时 ASR | 腾讯混元支持 Function Calling 的可购模型 | 腾讯云实时 TTS 预设音色 | **供应商对照**；端点、保留与合同需账户级确认 |
| 大陆候选 C | 百度 8 kHz 呼叫中心或实时 ASR | 百度千帆中支持 Function Calling 的可购模型 | 百度流式文本在线合成预设音色 | **第二对照**；电话采样率、音色和延迟需实测 |

选择依据：阿里 Fun-ASR 官方明确列出江苏、杭州、南京等地区官话口音，提供实时 WebSocket、热词及中文 8 kHz 型号；腾讯实时 ASR 官方列出南京、苏州、杭州、宁波、无锡等语音类型并支持 8/16 kHz、WebSocket 和热词。[阿里云 ASR 模型表](https://help.aliyun.com/zh/model-studio/asr-model/)；[阿里云实时 ASR 与区域](https://help.aliyun.com/en/model-studio/real-time-speech-recognition-user-guide)；[腾讯云实时 ASR API](https://cloud.tencent.com/document/api/1093/48982)；[腾讯云热词](https://cloud.tencent.com/document/product/1093/40996)

这只能证明“能力范围相符”，不能证明江浙口音电话准确率领先。Deepgram、Azure、Google、AWS 的文档普遍只列 `zh-CN`，没有发现江浙口音专项公开结果；它们只保留为未来海外研究背景，不能凭通用中文支持直接替代当前大陆候选的口音实测。[Deepgram 模型/语言](https://developers.deepgram.com/docs/models-languages-overview/)；[Azure 语言支持](https://learn.microsoft.com/en-au/azure/ai-services/speech-service/language-support)；[Google Recognizer API](https://docs.cloud.google.com/speech-to-text/docs/reference/rest/v2/projects.locations.recognizers)；[AWS Transcribe 语言表](https://docs.aws.amazon.com/transcribe/latest/dg/supported-languages.html)

## 2. Transcriber（STT）短名单

### 2.1 候选矩阵

| 供应商 | 与需求直接相关的官方证据 | 主要限制 / 待证实 | Demo 决策 |
|---|---|---|---|
| **阿里云 Model Studio Fun-ASR** | `fun-asr-realtime` 支持实时 WebSocket、热词、多语种及方言；文档点名江苏、杭州、南京等官话口音；另有 `fun-asr-flash-8k-realtime` 中文电话型号。北京和新加坡可用模型集合并不完全相同。[模型表](https://help.aliyun.com/zh/model-studio/asr-model/)；[实时 ASR/区域](https://help.aliyun.com/en/model-studio/real-time-speech-recognition-user-guide) | “江苏/杭州等口音”不是牙科 8 kHz 实测；大陆 Demo 必须显式使用北京 API Key 和端点，并核验口音覆盖与中英混说。 | **中文首选候选 A** |
| **腾讯云实时 ASR** | WebSocket；8/16 kHz 单声道；支持普通话、英语及南京、苏州、杭州、宁波、无锡、吴语等；支持医疗行业模型。热词可按音频流指定。[实时 API](https://cloud.tencent.com/document/api/1093/48982)；[热词](https://cloud.tencent.com/document/product/1093/40996) | 地方“方言模型”不等于带口音普通话；具体 engine、价格、处理与保留位置需控制台或合同确认。 | **中文对照候选 B** |
| **科大讯飞流式听写** | 支持 8/16 kHz、流式返回、个性化热词；官方列出普通话、中英混合和方言免切，后者包含南京话、上海话等；还有 `medical` 领域配置，但需单独授权。[服务说明](https://www.xfyun.cn/doc/asr/voicedictation/voicedictation-description.html)；[流式 API](https://www.xfyun.cn/doc/asr/voicedictation/API.html) | “实时语音转写标准版”页面要求 16 kHz；8 kHz 要选语音听写/坐席类能力。地区、并发、医疗能力授权不可只按通用价估算。 | **中文备选 C** |
| **百度实时/呼叫中心 ASR** | 官方实时接口采用 WebSocket；另列出面向呼叫中心的 8 kHz 商用识别能力。[实时识别概述](https://cloud.baidu.com/doc/SPEECH/s/qlcirqhz0)；[WebSocket API](https://cloud.baidu.com/doc/SPEECH/s/jlbxejt2i) | 通用实时接口文档以 16 kHz PCM 为主，电话 Demo 必须单独验证 8 kHz 产品、热词、并发和中英混说。 | **大陆中文对照 D** |
| **Deepgram Nova-3** | Nova-3 支持流式、`zh-CN`、`en-AU`、`en-US`、`en-GB`；Keyterm Prompting 可用于领域词；Flux 支持通话内语言提示动态更新，但其文档语言集合应逐模型核验。[模型/语言](https://developers.deepgram.com/docs/models-languages-overview/)；[Keyterm](https://developers.deepgram.com/docs/keyterm)；[Flux 语言切换](https://developers.deepgram.com/docs/flux/language-prompting) | 没有江浙口音专项证据；大陆处理端点和数据路径未证明。 | **未来海外研究；大陆 Demo 不准入** |
| **Azure Speech** | 官方语言表覆盖 `zh-CN` 与目标英语 locale，并逐 locale 标注 Phrase list / Custom Speech 可用性；适合统一国际供应商接口。[语言与音色支持](https://learn.microsoft.com/en-au/azure/ai-services/speech-service/language-support) | 必须逐 locale、逐部署区域核对 Phrase list/Custom Speech；无江浙专项证据。 | **未来海外研究；大陆 Demo 不准入** |
| **Google Cloud STT V2** | StreamingRecognize 返回部分/最终结果；Recognizer 支持多个 BCP-47 `languageCodes`、PhraseSet/CustomClass 适配，以及 LINEAR16、μ-law、A-law 解码配置。[Recognizer API](https://docs.cloud.google.com/speech-to-text/docs/reference/rest/v2/projects.locations.recognizers) | 多语言检测、适配、模型与区域可用性存在组合限制，需按目标 location 验证；无江浙专项证据。 | **未来海外研究；大陆 Demo 不准入** |
| **AWS Transcribe** | `zh-CN`、`en-AU`、`en-US`、`en-GB` 支持流式；自定义词表可用于支持的语言。[语言表](https://docs.aws.amazon.com/transcribe/latest/dg/supported-languages.html)；[自定义词表](https://docs.aws.amazon.com/transcribe/latest/dg/custom-vocabulary.html) | 流式语言识别不能同时选择同一语言的多个英语变体，且与部分自定义能力不能组合；中文高级能力少于英语。[流式语言识别限制](https://docs.aws.amazon.com/transcribe/latest/dg/lang-id-stream.html) | **未来海外研究；大陆 Demo 不准入** |

### 2.2 暂定推荐

1. 中文第一轮优先测 **阿里 Fun-ASR、腾讯实时 ASR、百度 8 kHz 呼叫中心 ASR**；讯飞在取得所需 8 kHz 与医疗能力授权后作为补充对照。全部使用相同 8 kHz μ-law/PCM 电话语料，不先下“最准确”结论。
2. 大陆候选还需分别测试英语输入和三种地区口音；如果供应商不能提供对应 locale，则记录为不支持，而不是自动改用境外 Provider。Deepgram、Azure、Google 和 AWS 只保留为未来海外研究候选。
3. 知识库发布后生成两份产物：给 LLM 的检索索引，以及给 STT 的经诊所管理员确认的热词/短语表。热词只能改善词项偏置，不能修复噪声、串音、口音或错误采样率。
4. 开场语言检测和通话中切换必须作为单独测试项。不要假设“模型支持多语”就等于中英 code-switch 在 8 kHz 下可用；AWS 已明确示例了自动语言识别与 locale/自定义能力的组合限制。[AWS 流式语言识别](https://docs.aws.amazon.com/transcribe/latest/dg/lang-id-stream.html)

## 3. Voice（TTS + 音色）短名单

| 供应商 | 与需求直接相关的官方证据 | 主要限制 / 待证实 | Demo 决策 |
|---|---|---|---|
| **阿里云 Qwen 实时 TTS** | WebSocket 双向流式输入/输出；可调语速、语调、音量、码率，支持 PCM/WAV/MP3/Opus；官方定位包含智能客服；北京端点有明确示例。[实时 TTS](https://help.aliyun.com/zh/model-studio/realtime-tts-user-guide) | 大陆 Demo 必须显式使用北京端点；中文预设音色、8 kHz/μ-law 输出和电话侧转码仍需逐型号实测。 | **中文首选候选** |
| **腾讯云实时 TTS** | 官方提供 WebSocket 实时语音合成，支持中文普通话、英语和方言音色。[实时 TTS](https://cloud.tencent.com/document/product/1073/94308) | 具体音色授权、处理与保留区域、8 kHz 电话输出和首包延迟需账户级验证。 | **大陆 Voice 对照 B** |
| **百度流式文本在线合成** | 官方 WebSocket 接口支持边输入边返回合成音频，并支持多音字发音标注。[流式文本在线合成](https://cloud.baidu.com/doc/SPEECH/s/lm5xd63rn) | 预设音色自然度、电话转码、并发和商业条款需实测。 | **大陆 Voice 对照 C** |
| **ElevenLabs Flash v2.5** | 官方文档列中文及美国/英国/澳洲英语，流式 API，PCM、8 kHz μ-law/A-law 电话输出；付费计划生成音频可商业使用（前提是输入内容权利合法）。[TTS 能力/许可](https://elevenlabs.io/docs/overview/capabilities/text-to-speech)；[流式 API](https://elevenlabs.io/docs/api-reference/text-to-speech/stream) | 大陆处理端点和数据路径未证明；任意克隆音色不属于 Demo 范围。 | **未来海外研究；大陆 Demo 不准入** |
| **Azure Speech TTS** | 官方统一列出 `zh-CN` 与各英语 locale 的音色，并可按区域/端点查询可用音色。[语言与音色支持](https://learn.microsoft.com/en-au/azure/ai-services/speech-service/language-support) | 音色与功能不是所有区域一致。 | **未来海外研究；大陆 Demo 不准入** |
| **Amazon Polly** | 普通话、澳式/英式/美式英语均有预设音色；部分引擎支持实时/双向流式，标准/神经音色支持 8/16/22/24 kHz；生成式引擎可在新加坡使用。[音色表](https://docs.aws.amazon.com/polly/latest/dg/available-voices.html)；[生成式音色与区域](https://docs.aws.amazon.com/polly/latest/dg/generative-voices.html) | 普通话预设音色有限；未证明大陆处理路径。 | **未来海外研究；大陆 Demo 不准入** |
| **Deepgram Aura-2** | 流式 Voice API；英语有美、英、澳等口音音色。[音色表](https://developers.deepgram.com/docs/tts-models) | 当前官方语言页未列中文，且未证明大陆处理路径。 | **未来海外研究；大陆 Demo 不准入** |

Voice 不以供应商营销的“自然”作结论。首轮用同一脚本盲听并自动测量：首音频包、完整时长、断句、姓名/日期/金额/手机号/牙科术语发音、8 kHz 转码后 MOS、被打断后停止耗时。Demo 只开放有商业授权的预设音色；Voice ID、供应商、模型版本、语言/口音、速率范围和许可元数据必须绑定保存。

## 4. Model（Hosted LLM）短名单

平台的 RAG 应由自有知识库层完成：先按诊所/版本/权限检索，再把引用片段交给 LLM；不要让供应商托管知识库成为唯一事实源。所有预约工具参数必须用 JSON Schema 校验，策略引擎在模型之外执行权限、安全披露、医疗边界和二次确认。

| 供应商 | 官方能力证据 | 主要限制 / 待证实 | Demo 决策 |
|---|---|---|---|
| **Alibaba Cloud Model Studio / Qwen** | OpenAI-compatible 接口；Qwen 系列支持 Function Calling；Structured Output（JSON mode）；北京和新加坡使用不同 API key/端点。[Function Calling](https://help.aliyun.com/en/model-studio/qwen-function-calling)；[Structured Output](https://help.aliyun.com/en/model-studio/qwen-structured-output)；[区域端点示例](https://help.aliyun.com/en/model-studio/openai-compatible-conversations) | 大陆 Demo 必须显式使用北京端点；型号、工具/结构化输出组合会变化，需锁定快照并回归。 | **大陆 LLM 首选候选** |
| **Tencent Hunyuan** | 官方提供 OpenAI 兼容接口和 Function Calling 示例。[OpenAI 兼容接口](https://cloud.tencent.com/document/product/1729/111007)；[对话 API](https://cloud.tencent.com/document/product/1729/105701) | 产品正在向 TokenHub 迁移；具体可购模型、端点、保留和并发需按新账户确认。 | **大陆 LLM 对照候选** |
| **Baidu Qianfan** | 官方文档提供 Function Calling 和 JSON Schema 结构化输出能力。[Function Calling](https://cloud.baidu.com/doc/qianfan-docs/s/xm95lyys5)；[功能特性](https://cloud.baidu.com/doc/qianfan/s/rmh4stn7m) | 需在账户中确认具体可购模型、工具调用稳定性、处理区域和保留方式。 | **大陆 LLM 对照候选** |
| **OpenAI API** | Responses API 支持流式响应、工具调用与 Structured Outputs；适合用供应商无关工具 schema 包装。[Streaming](https://platform.openai.com/docs/guides/streaming-responses)；[Function Calling](https://platform.openai.com/docs/guides/function-calling)；[Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs) | 当前方案未证明大陆处理端点与数据路径。 | **未来海外研究；大陆 Demo 不准入** |
| **Google Gemini API / Vertex AI** | Function Calling 支持并行/组合调用，并可与结构化输出结合；工具调用可流式返回。[Gemini Function Calling](https://ai.google.dev/gemini-api/docs/function-calling) | 当前方案未证明大陆处理端点与数据路径。 | **未来海外研究；大陆 Demo 不准入** |

LLM 首轮测 2–3 个大陆组合：Qwen 北京端点、腾讯混元当前可购的 Function Calling 模型、百度千帆当前可购的 Function Calling 模型。评分重点不是通用榜单，而是中文客服对话、严格依知识库、有引用的“不知道”、预约/改期/取消工具参数正确率、紧急症状流程、Prompt injection、首 token、整轮 P95 和成本。模型生成的工具调用永远只是“提议”；平台校验并要求患者确认后才执行。

## 5. 中国大陆区域与数据处理约束

1. 当前 Demo 的应用、存储、备份、日志和模型处理全部限制在中国大陆，不建设雅加达链路。
2. **存储区与推理处理区仍是两个字段。** 阿里官方文档明确北京和新加坡使用不同 API Key 与端点，因此必须显式选择北京端点，不能依赖 SDK 默认值。[阿里实时 ASR 区域](https://help.aliyun.com/en/model-studio/real-time-speech-recognition-user-guide)；[阿里实时 TTS](https://help.aliyun.com/zh/model-studio/realtime-tts-user-guide)
3. Provider Adapter 必须记录 `storage_region`、`processing_endpoint`、`retention_mode`、`subprocessors`、`model_snapshot` 和 `region_eligibility`，不能只记录供应商品牌。
4. `CN_ALLOWED` 需要同时通过大陆端点、处理与保留区域、商业条款、真实网络和统一基准测试验证；任何一项缺证据都不得进入运行时白名单。
5. 供应商发生端点迁移、模型下线或平台迁移时自动撤销准入，必须重新验证后才能恢复。
6. 国际供应商继续保留在 Provider Registry 的研究区，但路由层不得把大陆请求自动降级到境外模型。

## 6. 证据缺口（必须保留在决策记录中）

- 没有供应商发布可直接横比的“同一江浙口音、8 kHz 电话、牙科词汇”CER/WER；目前不存在可据以宣布冠军的官方证据。
- 阿里文档点名江苏/杭州/南京官话口音，腾讯列出当地语音类型，但没有证明它们对“带江浙口音的普通话”而非地方方言的相对增益。
- 未核实每个大陆候选端点的精确处理位置、供应商侧保留方式、故障转移路径、DPA、SLA 和并发配额。
- 未核实每个 TTS 预设音色在客服商业使用中的具体授权边界、音色撤回机制，以及模型升级造成的音色漂移。
- 未得到 API key，故本文没有真实首包延迟、并发、错误率、单分钟成本或故障恢复数据。
- 公开英语数据只能做初筛；`en-AU`、`en-US`、`en-GB` 的正式结论仍需真实电话录音。

## 7. 取得 API Key 后的最小测试门槛

1. **固定数据集**：4–6 名江苏/浙江说话者，人工转写+复核；每种英语口音使用公开授权数据初筛。保留原始宽带版，并生成 8 kHz PCM、μ-law、可控噪声和丢包版本。
2. **STT**：CER/WER；姓名、手机号、日期时间、牙科术语关键字段准确率；部分/最终结果延迟；错误改写次数；中英切换；长连接和重连。每个 Provider 分别测“无热词/有热词”。
3. **Voice**：首音频包、实时率、打断停止耗时、8 kHz 可懂度、数字/日期/术语读法；至少 5 名盲听者，隐藏供应商名称。
4. **LLM**：场景集逐条重放，工具参数 schema 通过率、工具选择正确率、幻觉率、紧急流程召回、Prompt injection、安全拒答、首 token 和整轮 P95。
5. **端到端**：10 路稳定并发；用户说完至 AI 首音 Demo P95 ≤ 2 s；所有失败必须可降级且不得虚假宣称预约成功。
6. **成本**：按成功通话分钟核算 STT + LLM 输入/输出 + TTS + 电话线路 + 日志/录音，不只比较厂商标价。

## 8. 决策门槛

在以下条件满足前，推荐始终标为“暂定”：同一冻结语料、同一音频编码、同一热词清单、至少三次不同时段重复、P95 延迟与错误率同时达标、合同确认商业使用/大陆处理区域/保留、故障降级通过。只有通过这些门槛的配置才能标为 `CN_ALLOWED`。最终 Provider Registry 应允许平台管理员更换具体模型，诊所只看到业务档位和预设 Voice。
