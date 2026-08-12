# Vapi 类框架与 Fun-ASR 适配调研

> 调研日期：2026-07-30  
> 范围：以自建多租户 AI 电话客服平台为目标；仅引用官方文档、官方仓库和官方 API 页面。厂商能力描述不等同于实测准确率结论。

## 结论先行

**按“自建可长期运营的多租户电话平台”排序：① LiveKit Agents，② Pipecat，③ Dograh，④ TEN Framework，⑤ Bolna。** 若只复述截图中的四项顺序，则是 Pipecat、LiveKit、Dograh、Bolna；差异来自截图更偏重 Demo 开发速度，而本报告把自托管 SIP、生产扩缩容、可观测性和长期可维护性权重提高。

1. **生产底座首选：LiveKit Agents + 自托管 LiveKit/SIP。** 它把实时媒体、SIP、Agent worker 调度、负载均衡、Kubernetes、多区域和 STT/LLM/TTS 插件放在同一体系内，最适合长期承载“平台”，但诊所后台、多租户、计费、知识库和策略引擎仍需自研。LiveKit 官方明确支持自托管 Server、独立 SIP Server、Agent server，以及工具调用、打断和可观测性接口。[LiveKit Agents](https://docs.livekit.io/agents/) · [Self-hosting](https://docs.livekit.io/transport/self-hosting/) · [SIP Server](https://docs.livekit.io/transport/self-hosting/sip-server/)
2. **最快验证语音链路：Pipecat。** 它是 BSD-2 的 Python 流式流水线框架，供应商/传输插件最广，适合快速做 Fun-ASR、LLM、TTS A/B 测试；但原生电话底座依赖 Daily、Twilio、Telnyx、Plivo 等 transport/serializer，自托管调度和 SIP 基础设施不如 LiveKit 一体化。[Pipecat overview](https://docs.pipecat.ai/overview/introduction) · [官方仓库与集成清单](https://github.com/pipecat-ai/pipecat)
3. **最像开源 Vapi 产品壳：Dograh。** 它已有多租户风格的可视化工作流、模型配置、通话记录和 Docker 自托管，适合借鉴或做二次开发；但官方目前将语言能力表述为“English support (expandable)”，中文、Fun-ASR、自定义安全策略和生产扩缩容必须自行验证，不能直接当作已完成。[Dograh 官方仓库](https://github.com/dograh-hq/dograh) · [运行机制](https://docs.dograh.com/core-concepts/how-dograh-works)
4. **TEN Framework 是值得保留的第四候选。** 它有 RTC/WebSocket、SIP 扩展、VAD/Turn Detection、可视化扩展图和 Docker 自托管，中文生态友好；不过整体采用“Apache 2.0 加额外限制”的混合许可表述，正式采用前需逐目录核对许可证。[TEN 官方仓库](https://github.com/TEN-framework/ten-framework)
5. **Bolna 可作原型参考，不建议作为第一生产底座。** 开源编排层支持 JSON、Twilio/Plivo 和多种 ASR/LLM/TTS，但其 README 明示 hosted API/UI 为闭源，并且正在招募维护者；生产级多租户、观测、升级和中文适配风险更高。[Bolna 官方仓库](https://github.com/bolna-ai/bolna)
6. **扩展调研后，jambonz 应进入生产 PoC 决赛。** 它比 Pipecat/LiveKit 更偏电话基础设施，但已经包含 SIP/SBC、媒体转码、多租户、横向扩展、监控和自定义 STT/TTS WebSocket 接口；对“电话优先、运营商由第三方提供”的本项目很契合。限制是完整生产部署仍有较重的 VoIP 运维，部分新能力和中大型部署支持属于商业服务范围。[jambonz overview](https://docs.jambonz.org/guides/get-started/jambonz-overview) · [Custom STT](https://docs.jambonz.org/guides/features/custom-stt-providers) · [Deployment options](https://docs.jambonz.org/guides/get-started/deployment-options)

截图中的 `Pipecat > LiveKit > Dograh > Bolna` 更像“快速搭 Demo”的顺序，不是所有目标下的统一排名。对本项目，建议采用 **LiveKit 做媒体/电话/worker 底座，先用 Pipecat 做供应商基准原型**；若团队优先要可视化后台，可研究 Dograh UI/工作流，但不要让它直接决定底层媒体架构。

## 框架与托管平台要分开

| 类型 | 代表 | 能否作为自有平台代码底座 | 说明 |
|---|---|---:|---|
| 实时框架/基础设施 | LiveKit Agents、Pipecat、TEN | 是 | 自己负责租户、权限、计费、诊所后台和合规策略 |
| 开源产品壳 | Dograh、Bolna | 可以二次开发 | 更接近 Vapi 的配置体验，但要承担其既有架构和成熟度风险 |
| 托管平台 | Vapi、Retell、Pipecat Cloud、LiveKit Cloud | 否（只能集成） | 可作功能和体验基准；Retell 官方提供 SIP、自带电话、监控、历史记录和测试，但核心平台不是自托管代码。[Retell 官方介绍](https://docs.retellai.com/general/introduction) · [Retell SIP](https://docs.retellai.com/deploy/custom-telephony) |
| 电话/SIP 平台 | jambonz、Fonoster | 是，但仍需自研 Agent 与 SaaS 控制面 | 负责电话、号码、SIP、媒体流和部分多租户能力；不是现成的牙科 SaaS |
| PBX/媒体引擎 | Asterisk、FreeSWITCH | 只能作为底层组件 | 控制力最高，但打断、STT/LLM/TTS 编排、租户、计费和后台都要自行实现 |
| 工作流/RAG 辅层 | LangGraph、Temporal、n8n、Dify 等 | 只能作为辅层 | 适合异步任务、预约工具或知识库，不能承担实时音频、VAD、端点检测和 SIP 媒体主循环 |

## 五个候选的同维度比较

| 维度 | Pipecat | LiveKit Agents | Dograh | Bolna | TEN Framework |
|---|---|---|---|---|---|
| 定位 | Python 流式 pipeline SDK | 实时媒体基础设施 + Agent SDK | 开源 Vapi 类产品/工作流 | JSON 驱动编排平台 | 实时多模态扩展框架 |
| 电话/SIP | 通过 Daily/WebRTC 或 Twilio、Telnyx、Plivo、Vonage serializer；不是自带完整 SIP 核心 | 原生 SIP 入/出站；SIP Server 可自托管 | Twilio、Vonage、Telnyx 等；可转人工 | Twilio、Plivo；其他在 README 标为 coming soon | 官方 SIP Call 扩展示例；RTC 常用 Agora |
| STT/LLM/TTS | 100+ 服务；组件最容易替换 | 官方插件丰富，支持自定义 STT node/plugin | 全局模型 + agent override；宣称 BYO provider | 多家 provider，但列表和实现需逐项审计 | 图式 extension，可替换 STT/LLM/TTS |
| 打断/轮次 | VAD、pipeline frames、可插处理器；需要工程调参 | VAD、语义/声学 turn detector、adaptive interruption、历史截断；自托管时部分云增强能力不可用 | 基于 Pipecat 的实时链路；中文 backchannel 行为需实测 | 有流式编排，但官方 README 未给出同等级 turn/false-interruption 保证 | 独立 TEN VAD/Turn Detection，可扩展 |
| 工具/工作流 | Pipecat Flows、function calling、processor | 通用 tool use、handoff、workflow | 拖拽节点、条件边、webhook/MCP | agent JSON 和 function/tool 逻辑 | extension/graph 连接业务工具 |
| 可观测性 | OpenTelemetry、Sentry、服务连接事件、Whisker | Cloud 内置 transcript/trace/recording；自托管走 OpenTelemetry data hooks | run 保存 transcript、recording、提取字段、cost | 需自行核实和补齐生产观测 | 有扩展和部分音频指标，平台级观测需自建 |
| 扩缩容 | 自托管需自己做 worker scheduler；Pipecat Cloud 托管 | Agent worker 注册、调度、LB、Kubernetes、多区域能力完整 | Docker 快速，但大规模调度需验证 | Docker Compose 原型清晰，生产集群能力较弱 | Docker/容器部署；集群编排需自行设计 |
| 许可 | BSD-2 | Apache-2.0 | BSD-2 | MIT | Apache-2.0 + 部分额外限制，需法务核查 |
| 百炼 Fun-ASR 云适配 | **低—中工作量** | **中工作量** | **中—高工作量** | **中—高工作量** | **中工作量** |

LiveKit 的轮次检测支持 VAD、STT endpointing、模型检测与 adaptive interruption；其中 adaptive interruption 官方注明是 LiveKit Cloud 能力，自托管版本不能默认计入能力清单。[Turn detection](https://docs.livekit.io/agents/logic/turns/) · [Adaptive interruption](https://docs.livekit.io/agents/logic/turns/adaptive-interruption-handling/)

## 扩展架构图谱

下面按“它实际负责哪一层”分类。不同层级不能直接按 GitHub stars 或功能数量排成一个榜。

| 候选 | 类型 | 自托管/许可 | Fun-ASR 接法 | 本项目判断 |
|---|---|---|---|---|
| **jambonz** | 多租户 SIP/Voice AI 电话平台 | MIT core；可白标、自托管；生产部署支持有商业部分 | 官方 Custom STT WebSocket：平台送 8 kHz LINEAR16 与控制帧，适配器转发百炼并返回 interim/final JSON | **进入生产 PoC 决赛**；电话能力最完整，但需评估商业版边界和 VoIP 运维 |
| **Fonoster** | 可编程电话栈 + Autopilot | 开源、可自托管，内置 workspace/RBAC | 原生 speech vendor 暂无百炼；可用 audio stream 接自研 adapter | **第二梯队**；形态接近，但文档注明 KB 仍 disabled/coming soon，Stream 目前不支持向 caller 的 `IN` 方向，不宜直接定为核心。[Fonoster overview](https://docs.fonoster.com/introduction) · [Autopilot](https://docs.fonoster.com/concepts/autopilot) · [Streams](https://docs.fonoster.com/concepts/bidirectional-streams) |
| **Asterisk + ARI** | PBX/SIP/媒体引擎 | 开源、自托管 | ARI External Media 将指定 codec 的媒体送到自研 gateway；gateway 再接百炼 | **高控制、高工作量**；新 WebSocket channel 降低了 RTP 定时/封包负担，但仍没有 Agent、租户和产品后台。[External Media](https://docs.asterisk.org/Development/Reference-Information/Asterisk-Framework-and-API-Examples/External-Media-and-ARI/) · [WebSocket channel](https://docs.asterisk.org/Configuration/Channel-Drivers/WebSocket/) |
| **FreeSWITCH + ESL** | 运营商级媒体/PBX 引擎 | 开源版可自托管，另有企业版 | 用 Event Socket 控制通话，另建媒体流模块/gateway 接百炼 | **只在团队有强 VoIP 经验时选择**；能力深，但工程与运维负担最大。[FreeSWITCH manual](https://developer.signalwire.com/freeswitch/) · [Event Socket](https://developer.signalwire.com/freeswitch/integration/event-socket/) |
| **Agora Conversational AI Engine** | 托管 RTC/Voice AI 引擎 | 闭源托管；TEN 是其开源、自托管方向 | 需确认 BYOM/自定义 ASR 的企业接入协议；不能按开源 adapter 自由改 | **做全球网络与并发体验基准**，不作为“完全脱离平台”的核心；官方支持任意 LLM/voice、打断与 SIP/PSTN，但按分钟收费。[Agora Conversational AI](https://www.agora.io/en/conversational-ai/) · [Pricing](https://www.agora.io/en/pricing/agora-conversational-ai-platform/) |
| **Vocode Core** | Python 语音 Agent 库 | 开源 | 新写 transcriber adapter | **观察/不推荐新项目主干**；官方仓库已表示正在寻找社区维护者，活跃维护风险与 Bolna 类似。[Vocode repository](https://github.com/vocodedev/vocode-core) |
| **VoiceBlender** | SIP/WebRTC 音频桥接层 | 开源 Go 项目 | 插入自研 STT/Agent 服务 | **技术观察名单**；支持 SIP、PCMA/PCMU/Opus 与 Pipecat/Vapi agent，但项目较新，缺少本项目所需的多租户和生产证据。[VoiceBlender](https://voiceblender.org/) |
| **Retell / Bland / Synthflow / Vapi** | 托管 Vapi 类成品 | 闭源 SaaS | 通常只能用平台允许的 BYOK/custom provider 方式，编排仍留在厂商侧 | **只做产品、延迟和运维基准**；不能满足“自有编排核心”的最终目标。Vapi 官方也明确自定义模型后，endpointing/interruptions 等仍由 Vapi 基础设施执行。[Vapi data flow](https://docs.vapi.ai/security-and-privacy/data-flow) · [Retell custom telephony](https://docs.retellai.com/deploy/custom-telephony) |

### 三种可以真正落地的组合

1. **电话优先：jambonz + 自研 Agent Orchestrator + Fun-ASR Gateway。** jambonz 管 SIP/SBC/转码/号码/录音和基本租户；自研层管双层 prompt、安全策略、工具、RAG、日志与计费。这是新增候选中与牙科电话平台最贴近的组合。
2. **全球实时媒体优先：LiveKit SIP + LiveKit Agents + Fun-ASR Plugin。** 适合未来同时做网页、App 和电话，多区域 worker 的路径更清晰；平台控制面仍自研。
3. **验证优先：Pipecat + jambonz/LiveKit transport + 统一 STT Gateway。** Pipecat 用于快速替换和压测 STT/LLM/TTS，不让 Demo 代码直接成为长期多租户电话核心。

不建议同时让 LiveKit Agents 和 Pipecat 都负责同一通电话的 VAD、endpointing、打断与会话状态，否则会产生双重状态机。混合架构中必须明确：一个是唯一的实时编排者，另一个最多做 transport 或实验 harness。

### 推荐增加统一 STT Gateway

无论最终选 LiveKit、jambonz 还是 Pipecat，都建议把 Fun-ASR 放在内部统一接口后面：

`SIP/媒体层 → codec normalizer → STT Gateway → Fun-ASR / 腾讯 / Azure / Google → 统一 interim/final/usage/error 事件`

Gateway 负责 8/16 kHz 与 G.711/PCM 转换、热词词表、租户凭据、北京/新加坡路由、重连去重、超时 fallback、延迟与费用指标。这样诊所后台仍只看到业务化的“中文标准/江浙优化/英语 AU-US-GB”档位，底层模型切换不需要改 Agent 框架。

## Fun-ASR：先确认你使用的是哪一个

名称容易混淆：

- **阿里云百炼 `fun-asr-realtime`**：托管 WebSocket API，是本报告重点。
- **开源 FunASR / SenseVoice**：本地 CPU/GPU 推理。Pipecat 当前原生 `FunASRSTTService` 属于这一类，并且是 `SegmentedSTTService`：VAD 结束后处理完整片段，只接收 16-bit mono PCM 16 kHz；它**不是**百炼实时云 API。[Pipecat FunASR 官方文档](https://docs.pipecat.ai/api-reference/server/services/stt/funasr)

因此，“Pipecat 已支持 FunASR”不能被理解为“直接支持百炼 Fun-ASR Realtime”。

## 百炼 Fun-ASR Realtime 的能力与限制

### 适合本项目的部分

- 官方主版本声称支持普通话、吴语，以及南京、江苏、杭州等地区官话口音，另支持英语等多语种；这与江浙口音候选范围高度重合，但仍只是**候选资格**，不是牙科电话录音准确率证明。[阿里云 ASR 模型列表](https://help.aliyun.com/zh/model-studio/asr-model/)
- 实时 API 使用 WSS，音频以单声道 binary stream 发送，持续返回结果；服务端事件为 `task-started`、`result-generated`、`task-finished`、`task-failed`。[WebSocket API](https://help.aliyun.com/zh/model-studio/fun-asr-realtime-websocket-api) · [服务端事件](https://help.aliyun.com/en/model-studio/fun-asr-server-events)
- `fun-asr-realtime` 接受 PCM/WAV/MP3/Opus/Speex/AAC/AMR，官方音频规格写“任意采样率、时长不限”；另有电话专用 `fun-asr-flash-8k-realtime`，固定 8 kHz。[音频规格](https://help.aliyun.com/zh/model-studio/asr-model/)
- 支持预建热词表，适合把诊所名、医生名、治疗项目和药品名从知识库同步到 STT；热词权重为 1–5，且需与目标模型匹配。[热词/上下文增强](https://help.aliyun.com/en/model-studio/improve-asr-accuracy)

### 必须接受的限制

1. **8 kHz 与多语不能同时想当然。** `fun-asr-flash-8k-realtime` 官方语言是中文；若一通电话需要中英切换，需测试通用 `fun-asr-realtime` 直接吃 8 kHz/上采样后的效果，或按语言路由另一 STT。不能因为 API 接受“任意采样率”就推断 8 kHz 英语准确率良好。
2. **英语没有 AU/US/GB locale 模型选择。** 官方仅列 English，并未提供 `en-AU`、`en-US`、`en-GB` 三个明确 locale。因此它可进入英语基准测试，但不应成为三种英语口音的唯一供应商。
3. **实时版不提供说话人分离或情绪识别。** 官方模型表将两项标为 unsupported；电话客服通常是双通道媒体，可由通道区分双方，但转接、会议式多方通话不能依赖 Fun-ASR 自己做 diarization。
4. **热词有区域/空间限制。** 新加坡支持的实时热词模型少于北京，而且官方明确写明“新加坡子业务空间不支持热词”。多租户设计不能简单地给每家诊所创建 sub-workspace 再期望热词可用；应验证主 workspace 下的租户隔离和词表配额。[热词区域限制](https://help.aliyun.com/en/model-studio/improve-asr-accuracy)
5. **SDK 与协议适配。** DashScope SDK 仅官方支持 Java/Python；TypeScript/其他语言要直接实现 WSS 握手、`run-task`/binary audio/`finish-task` 和四类服务端事件。[WebSocket API](https://help.aliyun.com/zh/model-studio/fun-asr-realtime-websocket-api)
6. **“时长不限”不等于永不重连。** 官方模型规格没有单通电话时长上限，但工程上仍需处理 WebSocket 握手失败、`task-failed`、网络抖动、重连、重复结果、最终结果提交和 provider fallback。

## 雅加达部署的实际数据路径

百炼 Fun-ASR 实时端点只有 **北京**和**新加坡**；官方没有雅加达推理端点。新加坡端点为 `ap-southeast-1`，北京与新加坡 API Key/Workspace 分区。[Fun-ASR WebSocket 端点](https://help.aliyun.com/zh/model-studio/fun-asr-realtime-websocket-api)

若所有编排与存储都在雅加达，典型中国大陆来电会形成：

`中国运营商/SIP 媒体 → 雅加达编排 → 新加坡 Fun-ASR → 雅加达 LLM/TTS/编排 → 中国电话`

这意味着音频可能先离开中国、再跨区域到新加坡；若改用北京 Fun-ASR，则是雅加达与北京之间持续双向传输。哪条更快不能凭地理位置下结论，必须用真实 SIP 线路分别测 `media RTT`、STT 首个 partial、final latency、丢包和 P95 用户停说到 TTS 首包。建议把媒体 worker 做成区域化：**中国来电优先中国/邻近媒体节点，控制面仍可在雅加达**；如果坚持全部在雅加达，P95 2 秒目标应作为上线门槛而不是预设结果。

## 各框架接百炼 Fun-ASR 的工作量

- **jambonz（低—中）**：不必修改电话核心；实现官方 Custom STT WebSocket 服务即可。jambonz 固定发送 8 kHz LINEAR16，adapter 映射成百炼 binary audio 与任务事件，再把 partial/final/confidence 映射回 jambonz transcription JSON。需要补热词 `vocabulary_id`、区域路由、重连与租户凭据。[Custom STT protocol](https://docs.jambonz.org/guides/features/custom-stt-providers)
- **Pipecat（最低）**：新建云端 `STTService`，把 pipeline PCM frame 转为百炼要求的单声道 binary，映射 partial/final `result-generated` 为 transcription frames，并实现连接/失败事件、热词 ID、语言 hint 和重连。Pipecat 已有 WebSocket STT 基类事件与 OpenTelemetry，最适合先完成适配和基准。[Service events](https://docs.pipecat.ai/server/utilities/service-events) · [OpenTelemetry](https://docs.pipecat.ai/api-reference/server/utilities/opentelemetry)
- **LiveKit（中）**：实现继承 `STT`/`RecognizeStream` 的 provider plugin，把音频 frame 推入百炼 WSS，并输出 `SpeechEvent`（interim/final/usage/error）。LiveKit 官方明确支持自定义 STT node，且流式接口会自动做目标采样率重采样。[Custom STT](https://docs.livekit.io/agents/models/stt/) · [Python STT API](https://docs.livekit.io/reference/python/livekit/agents/stt/index.html)
- **Fonoster（中—高）**：可用 `Stream` 接出 caller audio，再由外部服务连接百炼；但其当前 Stream 文档明确写了尚不支持向 caller 的 `IN` 方向，因此完整双向 Agent 不应只依赖该接口，需结合 Say/Play 或修改底层。
- **Asterisk/FreeSWITCH（高）**：除 Fun-ASR adapter 外，还需自己做媒体定时/缓冲、VAD/endpointing、打断、TTS 回注、故障恢复与并发调度。它们是电话引擎，不是现成 Voice Agent runtime。
- **TEN（中）**：按扩展协议新增阿里云 STT extension，接入现有 RTC/SIP、VAD/turn detection 图；扩展方式自然，但团队需熟悉 TEN runtime 和属性/消息协议。
- **Dograh（中—高）**：它建立在 Python/Pipecat 语音链路上，可复用 Pipecat adapter，但还要补 dashboard provider schema、密钥、全局/agent override、诊所热词词表、迁移和审计。官方现有模型配置只是“可选 provider”，不代表阿里百炼已原生支持。[Dograh 模型配置](https://docs.dograh.com/configurations/inference-providers)
- **Bolna（中—高）**：需实现 transcriber provider、配置校验、WebSocket 生命周期和电话采样率转换；同时要自行补足测试、指标和故障切换。其开源核心可改，但 hosted API/UI 并不开源。

## 更适配的 STT 候选池（不是排名）

### 江浙口音普通话 / 中文电话

1. **阿里 `fun-asr-realtime` + `fun-asr-flash-8k-realtime`**：分别测试通用口音覆盖和 8 kHz 中文电话专用模型。
2. **腾讯云实时 ASR**：官方明确列出南京话、苏州话、杭州话、宁波话、无锡话、吴语等，并给出 8 kHz PCM 包发送规范；因此非常值得与 Fun-ASR 做同一录音 A/B，但不能仅凭语言列表断言更准。[腾讯实时 ASR WebSocket](https://cloud.tencent.com/document/api/1093/48982)
3. **Azure Speech `zh-CN`**：作为国际云对照组；支持 phrase list/custom speech，但官方没有“江浙口音专用 locale”的承诺。[Azure 语言支持](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support)

### en-AU / en-US / en-GB

1. **Azure Speech**：官方明确提供 `en-AU`、`en-US`、`en-GB` 实时 locale，并支持 phrase list/custom speech，最适合作为三种英语口音的基准主候选。[Azure 语言支持](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support)
2. **Google Cloud Speech-to-Text**：官方语言表提供区域化英语模型，并有 telephony/telephony_short 与 PhraseSet/model adaptation；需按目标 region 检查具体模型可用性。[Google STT 语言/模型](https://docs.cloud.google.com/speech-to-text/docs/speech-to-text-supported-languages) · [Model adaptation](https://docs.cloud.google.com/speech-to-text/docs/adaptation-model)
3. **Fun-ASR Realtime**：作为统一多语模型对照组，不作为三种英语 locale 的唯一依据。

最终选择必须使用同一批 8 kHz 真人电话录音计算中文 CER、英文 WER、姓名/电话/日期/牙科术语关键字段准确率，以及 partial/final latency、连接失败率和每分钟成本。供应商官方“支持某口音/语言”只证明可以测试，不证明质量领先。

## 建议的两阶段落地

### 阶段 A：两周技术验证

- 用 Pipecat 实现百炼 Fun-ASR 云 adapter，同时接入腾讯和 Azure；固定一套 STT frame/result 接口。
- 将同一 SIP 录音分别送入通用 Fun-ASR、8k Fun-ASR、腾讯 ASR、Azure/Google；记录 CER/WER、关键字段和端到端 P95。
- 分别从雅加达到新加坡/北京端点测持续流，不用 `ping` 代替真实音频链路。
- 验证中文“嗯、好的、对”等 backchannel 不打断，以及真正插话停止 TTS 的时延。

### 阶段 B：平台底座

- 对两个生产候选做 3–5 天电话 PoC：**LiveKit Agents + 自托管 SIP/worker** 与 **jambonz + 自研 Agent Orchestrator**。同一 SIP 线路、同一 Fun-ASR Gateway、同一并发与故障场景对比，不先凭框架介绍定案。
- 管理后台只暴露业务档位；平台内部维护 `Transcriber + Model + Voice` 兼容配置包和 fallback。
- Dograh 只作为可视化工作流、通话记录页和 provider 配置页的产品参考；除非代码审计、中文测试和扩缩容 PoC 通过，否则不直接 fork 为核心。

## 最终推荐

**平台架构决赛：LiveKit Agents（全球实时媒体优先）与 jambonz（SIP/PSTN 电话优先），用短期 PoC 定案；两者之外统一自研多租户控制面。**  
**原型/模型测试：Pipecat。**  
**首批中文 STT：Fun-ASR Realtime 与腾讯实时 ASR 双候选；8 kHz 中文另测 Fun-ASR Flash 8K。**  
**英语 STT：Azure 为 en-AU/en-US/en-GB 主候选，Google 为对照。**  
**Fonoster：第二梯队；Dograh：参考或受控二次开发；Bolna/Vocode：原型参考；TEN/Agora：若团队偏好 Agora 生态，再做 PoC。**

在没有同一批真实电话数据和 API 实测前，不给出“Fun-ASR 最准”或“腾讯/Azure 更准”的结论。
