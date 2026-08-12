# 极简 STT → LLM → TTS 语音问答设计

## 目标

在 `E:\YinoVapi\Voice-STT-LLM-TTS-HelloWorld` 新建一个独立的本地原型，实现完整的中文语音问答闭环：

1. 浏览器录制一段语音。
2. 后端将音频提交给 STT 模型并取得文字。
3. 后端将识别文字提交给 LLM 并取得回答。
4. 后端将回答提交给 TTS 模型。
5. 页面同时显示识别文字、回答文字，并自动播放回答语音。

## 范围

原型只包含单轮语音问答，不包含登录、数据库、会话历史、实时字幕、流式 LLM、流式 TTS、打断、多租户、部署或自动化测试。

## 模型

- STT：阿里云百炼 `qwen3-asr-flash`
- LLM：阿里云百炼 `qwen3.7-flash`
- TTS：阿里云百炼 `qwen3-tts-flash`
- TTS 默认音色：`Cherry`
- 默认语言：中文

选择 `qwen3-asr-flash` 是因为它支持短录音的 HTTP/OpenAI 兼容调用、WebM 音频和 Base64 输入，适合“说完一句再回答”的极简流程。`fun-asr-realtime` 暂不接入；它需要 Workspace WebSocket、PCM 音频流和更复杂的会话管理。

## 结构

```text
Voice-STT-LLM-TTS-HelloWorld/
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
└── app/
    ├── __init__.py
    ├── config.py
    ├── bailian.py
    ├── main.py
    └── static/
        ├── index.html
        ├── app.js
        └── styles.css
```

FastAPI 同时提供静态页面和一个语音问答接口。`bailian.py` 直接封装三个顺序调用，不引入 Provider Factory 或其他扩展层。

## 数据流

浏览器使用 `MediaRecorder` 生成 WebM/Opus 音频，并通过 `multipart/form-data` 上传到 `POST /api/voice-chat`。

后端按以下顺序处理：

```text
WebM 音频
  → qwen3-asr-flash
  → transcript
  → qwen3.7-flash
  → reply
  → qwen3-tts-flash
  → audio URL
```

接口成功响应：

```json
{
  "transcript": "用户说的话",
  "reply": "模型回答",
  "audio_url": "https://...",
  "timings_ms": {
    "stt": 0,
    "llm": 0,
    "tts": 0,
    "total": 0
  }
}
```

页面收到响应后更新识别文字和回答文字，将 `audio_url` 设置给音频元素并尝试自动播放。浏览器阻止自动播放时，用户仍可点击播放器手动播放。

## 配置与安全

`.env` 只保存在本机并被 Git 忽略：

```env
DASHSCOPE_API_KEY=
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
STT_MODEL=qwen3-asr-flash
LLM_MODEL=qwen3.7-flash
TTS_MODEL=qwen3-tts-flash
TTS_VOICE=Cherry
```

API Key 不进入 HTML、JavaScript、URL、响应或日志。TTS 返回的音频 URL 有时效性；原型不下载或持久化音频。

## 错误处理

- 缺少 API Key：返回明确的 `503` 配置错误。
- 不支持的音频格式、空音频或超过 10 MB：返回 `400`。
- STT、LLM 或 TTS 调用失败：返回 `502`，页面显示当前失败阶段。
- STT 返回空文字：不继续调用 LLM 和 TTS。
- LLM 返回空回答：不继续调用 TTS。

页面在失败后恢复到可重新录音状态，并停止占用麦克风。

## 完成标准

- `GET /health` 返回正常状态。
- 页面可以录制不超过 60 秒的中文语音。
- 一次点击流程能显示识别文字和 LLM 回答。
- 成功时可播放 TTS 回答音频。
- 源码和页面均不包含真实 API Key。
- 中文界面与错误信息以 UTF-8 正常显示。
- README 给出 Windows 下创建虚拟环境、安装依赖、配置 `.env` 和启动服务的最短步骤。

## 验证方式

按用户要求不创建自动化测试。完成后只做以下手工验证：

1. 启动服务并访问首页。
2. 检查 `/health`。
3. 使用真实凭据录制一句中文。
4. 确认识别文字、回答文字和回答音频均成功返回。

