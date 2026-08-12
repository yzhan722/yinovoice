# LiveKit 本地语音闭环设计

## 目标

建立一个最小、可独立运行的 LiveKit Agents 技术基底，验证：

`本地麦克风 → STT → LLM → TTS → 本地扬声器`

该阶段只证明实时语音 Agent 主链路可用，并为后续浏览器前端和 SIP 电话入口保留稳定扩展点。

## 范围

### 本阶段包含

- Python LiveKit Agents Agent。
- LiveKit `console` 模式本地麦克风输入与扬声器输出。
- 阿里云百炼 Fun-ASR STT 适配器，以及独立的 LLM、TTS 配置。
- 简短中文系统指令和首次问候。
- 用户插话时停止当前 TTS 的基础打断行为。
- 环境变量配置和启动说明。
- 不调用真实模型的自动化测试。
- 为后续前端提供可复用的 Agent 构建函数。

### 本阶段不包含

- 平台前端、用户登录或多租户。
- LiveKit Cloud 房间和浏览器 WebRTC。
- SIP 电话呼入、呼出和转人工。
- 知识库、预约、Function Tools。
- 会话数据库、录音、计费或数据分析。
- Fun-ASR 原生流式 partial 字幕；第一阶段先由 LiveKit VAD 切分单次发言，再调用 Fun-ASR 返回 final 文本。
- 自托管 LiveKit Server、SIP Server、Redis 或 TURN。

## 技术选择

| 部分 | 第一阶段选择 |
|---|---|
| 语言 | Python 3.11+ |
| Agent runtime | LiveKit Agents Python |
| 音频入口/出口 | LiveKit `console` 模式 |
| 模型接入 | 直接使用模型供应商插件，不使用 LiveKit Inference |
| STT | 阿里云百炼 `fun-asr-realtime`，北京端点 |
| LLM / TTS | OpenAI 直连插件 |
| 配置 | `.env.local` 环境变量 |
| 测试 | pytest，模型与实时会话使用替身 |

第一阶段直接验证项目首选中文 STT：Fun-ASR。为控制适配工作量，Fun-ASR 先实现 LiveKit 非流式 STT 接口，由 Silero VAD 在用户停说后提交完整发言；这能完成真实语音闭环和基础打断，但不会提供逐字 partial 字幕。第二阶段浏览器字幕接入前，再把同一适配器升级为原生流式接口。LLM 和 TTS 暂用 OpenAI 直连插件，三类模型仍通过 Provider Factory 隔离。

## 目录结构

在现有项目旁创建独立目录，避免修改当前非实时探针：

```text
YinoVoicePlatform/
└── voice-agent/
    ├── src/
    │   └── yino_voice_agent/
    │       ├── __init__.py
    │       ├── assistant.py
    │       ├── config.py
    │       ├── fun_asr.py
    │       ├── providers.py
    │       ├── session.py
    │       └── server.py
    ├── tests/
    ├── .env.example
    ├── .gitignore
    ├── pyproject.toml
    └── README.md
```

各模块职责：

- `config.py`：读取并验证环境变量，不创建网络客户端。
- `fun_asr.py`：把 LiveKit 音频缓冲转换为 Fun-ASR 可识别的音频并返回标准 STT 事件。
- `providers.py`：创建 Fun-ASR STT、OpenAI LLM 和 OpenAI TTS，实现模型供应商隔离。
- `assistant.py`：定义 Agent 指令。
- `session.py`：组合 STT、LLM、TTS 和 VAD。
- `server.py`：提供 LiveKit `console` CLI 入口。
- `tests/`：验证配置、Agent 指令和 Provider 注入，不消费真实额度。

## 运行架构

```text
LiveKit console audio
        ↓
     AgentSession
        ├── Silero VAD → Fun-ASR STT Adapter
        ├── LLM Provider
        ├── TTS Provider
        └── VAD / interruption handling
        ↓
LiveKit console playback
```

`AgentSession` 是唯一的实时会话状态机。本阶段不在外围重复实现 VAD、端点判断、播放队列或打断状态。

## 配置接口

必须支持以下环境变量：

```env
DASHSCOPE_API_KEY=
DASHSCOPE_WEBSOCKET_URL=
FUN_ASR_MODEL=fun-asr-realtime
OPENAI_API_KEY=
LLM_MODEL=
TTS_MODEL=
TTS_VOICE=
AGENT_LANGUAGE=zh-CN
```

`.env.example` 提供北京区域 Fun-ASR WebSocket 地址格式和可运行的默认模型名称，但不包含 Workspace ID 或真实密钥。缺少任一 API Key、Workspace URL 时，程序应在启动模型会话前返回明确错误。

## Agent 行为

- 使用标准普通话。
- 回复简洁，通常不超过两句话。
- 不声称具备本阶段未实现的知识库、预约或电话能力。
- 启动后主动进行一句简短问候。
- 用户真正插话时允许打断回复。
- “嗯、好的”等短促附和的特殊处理不属于第一阶段验收范围。

## 错误处理

| 情况 | 行为 |
|---|---|
| 缺少 API Key 或 Workspace URL | 启动失败并指出缺少的变量 |
| 配置为空或模型名无效 | 配置加载失败，不进入音频会话 |
| STT/LLM/TTS 请求失败 | 记录供应商和阶段，不输出密钥 |
| 麦克风不可用 | 由 console runtime 报错，README 提供排查步骤 |
| 用户中断程序 | 正常关闭 AgentSession |

日志禁止输出 API Key、完整鉴权头或原始环境变量。

## 测试与验收

### 自动化测试

- 完整配置可以成功加载。
- 缺少 `DASHSCOPE_API_KEY`、`DASHSCOPE_WEBSOCKET_URL` 或 `OPENAI_API_KEY` 时返回明确错误。
- Fun-ASR 适配器把 LiveKit 音频转换为 final transcript，且测试不访问网络。
- Agent 使用预期中文指令。
- Provider Factory 接收配置并创建三类模型对象。
- 测试不得发起真实模型请求。

### 手工验收

运行：

```powershell
python -m yino_voice_agent.server console
```

通过标准：

1. 程序能够访问本机麦克风。
2. Agent 主动播放中文问候。
3. 用户说一句中文后能看到 Fun-ASR 识别文本。
4. Agent 生成中文回答并通过扬声器播放。
5. 用户在 Agent 说话时插话，当前播放能够停止并处理新输入。
6. 连续进行至少三轮对话，进程不崩溃。

## 后续扩展

第二阶段增加浏览器前端时：

- 保留 `config.py`、`providers.py` 和 Agent 定义。
- 将同一 AgentServer 从 `console` 模式切换到 LiveKit 房间。
- 后端增加 Session Token API。
- 前端使用 LiveKit SDK 传输麦克风和播放 Agent 音频。

电话阶段再把 SIP participant 接入同一个 LiveKit 房间，不改变 STT、LLM、TTS 或 Agent 业务逻辑。

## 成功边界

第一阶段成功只代表本地语音闭环和 Fun-ASR final 转写可用，不代表原生流式 partial 字幕、浏览器、LiveKit Cloud、自托管媒体服务器或电话链路已经验证。
