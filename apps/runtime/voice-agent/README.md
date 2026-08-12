# Yino LiveKit 实时语音客服 Worker

默认运行路径是 Qwen Audio Realtime，而不是拆分式 STT/LLM/TTS pipeline：

```text
浏览器麦克风 → LiveKit → Qwen Audio Realtime → LiveKit 立即回放 → 浏览器扬声器
```

默认模型为 `qwen-audio-3.0-realtime-plus`，音色为 `longanqian`。输入音频转换为 16 kHz、单声道 PCM16，并按 640 samples（40 ms）发送。Qwen 会话启用 `smart_turn`、用户 partial/final 转写、客服增量文本和音频，以及用户说话时的 barge-in。

服务端收到 `response.audio.delta` 后会立即把 PCM 帧转交 LiveKit，**不会等待 `response.done` 才播放**。打断会取消当前响应并抑制该响应随后迟到的文字/音频，避免旧回复重新播放或堆积。

## 前置条件和安装

支持 Python 3.11–3.14。需要本地 LiveKit、有效 DashScope Qwen Realtime 凭据，以及可用的麦克风和扬声器。

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

默认源遇到 TLS 问题时可使用阿里云镜像回退：

```powershell
.\.venv\Scripts\python.exe -m pip install `
  -i https://mirrors.aliyun.com/pypi/simple/ `
  --trusted-host mirrors.aliyun.com `
  -e ".[dev]"
```

## 本地配置

```powershell
Copy-Item .env.example .env.local
```

`.env.local` 已被忽略，只供本机使用，不应提交、打印或分享。示例中的 LiveKit `devkey` / `secret` 只适用于本机 `livekit-server --dev`。

必须在 `.env.local` 中替换以下两个占位值：

```dotenv
DASHSCOPE_API_KEY=replace-with-your-valid-local-value
QWEN_REALTIME_URL=wss://replace-with-your-valid-workspace-host/api-ws/v1/realtime
```

默认配置保持为：

```dotenv
VOICE_PROVIDER_MODE=qwen-realtime
QWEN_REALTIME_MODEL=qwen-audio-3.0-realtime-plus
QWEN_REALTIME_VOICE=longanqian
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
PLATFORM_API_URL=http://localhost:8000
ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV=false
```

不要把真实 key 写入 `.env.example`、README、日志、验收报告或前端 `VITE_` 变量。

## 启动 named worker

先启动 LiveKit 和 Platform API，然后在本目录运行：

```powershell
.\.venv\Scripts\python.exe -m yino_voice_agent.server dev
```

worker 以 `yino-customer-service` 注册。Platform API 创建 dispatch，并携带客服 ID、Tenant ID 和配置版本；worker 只接受匹配的配置快照。正常 `dev` worker 必须保持 `ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV=false`。

## 可选本机 console

console 用于直接检查本机音频设备，不经过浏览器；它仍会使用真实 Qwen 凭据并消耗额度。

```powershell
$env:ALLOW_EMPTY_DISPATCH_METADATA_LOCAL_DEV='true'
.\.venv\Scripts\python.exe -m yino_voice_agent.server console --list-devices
.\.venv\Scripts\python.exe -m yino_voice_agent.server console
```

只在有意运行 console 的当前终端中临时开启该变量，不要用于 named RTC worker。

## 可选 pipeline fallback

`Fun-ASR + LLM + TTS` 不是默认 Demo 链路。需要回退时，在 `.env.local` 中把 `VOICE_PROVIDER_MODE` 改为 `pipeline`，并配置示例中注释掉的这些项目：

```dotenv
VOICE_PROVIDER_MODE=pipeline
DASHSCOPE_WEBSOCKET_URL=wss://replace-with-your-valid-workspace-host/api-ws/v1/inference
FUN_ASR_MODEL=fun-asr-realtime
OPENAI_API_KEY=replace-with-your-valid-local-value
LLM_MODEL=gpt-4o-mini
TTS_MODEL=gpt-4o-mini-tts
TTS_VOICE=ash
```

pipeline fallback 的行为和延迟不能代表 Qwen Realtime 默认链路。

## 安全排障

| 现象 | 安全检查方式 |
|---|---|
| worker 未被调度 | 核对 LiveKit 是否运行、Platform API 是否可访问，以及双方 agent name 是否为 `yino-customer-service` |
| 启动时报配置错误 | 只确认所需变量是否存在、占位值是否已替换、URL 是否为 `wss://`；不要把值粘贴到终端记录 |
| 有转写但没有声音 | 检查扬声器、浏览器自动播放权限、系统音量和当前会话状态 |
| 无用户转写 | 检查麦克风权限、输入设备和音轨发布状态 |
| 打断后仍听到旧音频 | 记录非敏感时间点和组件版本后停止验收；不要记录原始 provider payload |
| Provider 连接失败 | 在供应商控制台检查额度、区域和模型权限；日志只保留稳定错误类别，不回显 key、URL 查询参数或原始响应 |

真实五轮验收需要 `livekit-server`、有效本地 Qwen 环境、浏览器、麦克风和扬声器全部可用。缺少任一条件时记录 **NOT EXECUTED**，不要用单元测试替代。

## 自动化验证

测试使用本地 fake，不连接供应商，也不消耗模型额度：

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m ruff check --no-cache src tests
.\.venv\Scripts\python.exe -m yino_voice_agent.server --help
```

电话、SIP、Jambonz、预约和知识库当前均未连接到本 worker。
