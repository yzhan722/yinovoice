# Fun-ASR 实时语音转写界面设计

- 日期：2026-07-28
- 状态：已确认，待实现计划
- 范围：本地可运行的单用户语音输入与实时 STT 输出原型
- 供应商基线：阿里云百炼 `fun-asr-realtime`

## 1. 目标

搭建一个浏览器界面，让用户授权麦克风后开始或停止录音，并在页面中实时看到 Fun-ASR 返回的临时转写和最终句子。原型用于验证浏览器录音、Python Provider Adapter、流式事件展示和基础延迟指标，不包含登录、多租户、通话接入、持久化数据库或生产部署。

## 2. 官方 SDK 约束

- API Key 只从后端环境变量 `DASHSCOPE_API_KEY` 读取，不进入浏览器代码、日志或响应。
- 第一版地域固定为华北 2（北京）。后端从 `DASHSCOPE_WORKSPACE_ID` 读取业务空间 ID，并使用 `wss://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference`；北京地域 API Key 必须与该业务空间匹配。
- 后端使用 DashScope Python SDK 的 `Recognition`、`RecognitionCallback`、`start()`、`send_audio_frame()` 和 `stop()`。
- 浏览器发送单声道、16 kHz、16-bit PCM 音频；每个分片约 100 ms。
- 后端通过 `on_event` 读取 `RecognitionResult.get_sentence()`。
- `RecognitionResult.is_sentence_end(sentence)` 为真时，将结果作为最终句子；否则作为当前临时结果。
- 第一版采用 VAD 断句：`semantic_punctuation_enabled=False`，静音阈值默认 1,000 ms，并允许在 200–6,000 ms 范围内配置。
- 第一版默认 `language_hints=["zh"]`，界面允许选择自动识别、中文或英文；只向 SDK 发送一个语言提示值。
- SDK 或服务错误保留 `request_id` 供排障，但不得记录 API Key 或原始音频内容。

## 3. 架构与模块边界

### 3.1 Web 前端

职责：

- 请求麦克风权限。
- 使用 Web Audio API 将输入转换为 16 kHz 单声道 PCM16。
- 通过浏览器 WebSocket 向本地后端发送音频分片。
- 展示连接、录音、识别、完成和错误状态。
- 分开展示临时结果与已经确认的最终句子。

前端不依赖 DashScope SDK，也不知道阿里云 API Key。

### 3.2 Python WebSocket 后端

职责：

- 接受一个浏览器转写会话。
- 校验开始事件中的语言和静音阈值。
- 为该会话创建独立的 Fun-ASR Recognition 实例。
- 将二进制音频帧传给 `send_audio_frame()`。
- 将 SDK 回调转换为供应商中立的前端事件。
- 在用户停止、浏览器断开或服务报错时可靠关闭 Recognition 会话。

### 3.3 Fun-ASR Adapter

职责：

- 封装 DashScope SDK 及地域配置。
- 将供应商结果转换为统一的 `partial`、`final`、`metric` 和 `error` 事件。
- 隔离供应商字段，避免页面直接依赖 `RecognitionResult`。

## 4. WebSocket 协议

浏览器发送：

- JSON `start`：包含 `sampleRate=16000`、`language`、`maxSentenceSilenceMs` 和可选 `vocabularyId`。
- Binary：PCM16 音频分片。
- JSON `stop`：结束本次转写。

后端发送：

- `session.started`：会话和供应商连接已准备好。
- `transcript.partial`：当前未结束句子的完整替换文本。
- `transcript.final`：最终句子，包含文本、开始时间和结束时间。
- `session.metric`：`requestId`、首包延迟和尾包延迟；不存在的值使用 `null`。
- `session.completed`：服务已处理完全部音频。
- `session.error`：稳定错误码、用户可读消息和可选 `requestId`。

临时结果采用替换语义，而非追加语义；最终句子仅追加一次。这样可以避免 SDK 对同一句子的中间结果在界面中重复。

## 5. 界面设计

页面使用单屏工作台布局。

### 5.1 顶部状态栏

- 产品名称：实时语音转写实验台。
- Provider/Model：Alibaba Cloud / `fun-asr-realtime`。
- 状态徽标：未连接、已连接、正在录音、正在收尾、已完成或出错。
- 指标：音频规格、首包延迟和当前会话时长。

### 5.2 左侧录音控制

- 大号圆形麦克风按钮作为主操作。
- 实时音量波形或电平条，帮助用户确认麦克风正在收音。
- 明确的“开始录音”和“停止并完成”标签。
- 麦克风权限、设备不可用和静音状态的就地提示。
- 折叠设置：语言、静音断句阈值和可选热词 ID。

### 5.3 右侧转写画布

- 最终句子按时间顺序显示，带句子起止时间。
- 临时结果固定显示在列表底部，采用较浅颜色和闪动光标；收到最终句子后清空。
- 空状态提示用户点击麦克风开始说话。
- 提供复制全文、清空当前页面和下载 `.txt`。
- 页面不保存原始音频；刷新后转写内容清空。

### 5.4 视觉方向

- 使用温和的浅色工作台风格，避免仿聊天窗口。
- 主色用于麦克风和活动状态；错误、警告和成功状态保持高辨识度。
- 录音按钮、状态文本和音量变化同时表达录音状态，不仅依赖颜色。
- 桌面端采用左右双栏，小屏改为录音区在上、转写区在下。

## 6. 状态机

`idle → connecting → recording → stopping → completed`

任意活动状态均可进入 `error`。错误后用户可以重置回 `idle` 并重新开始。连接建立之前不发送音频；进入 `stopping` 后不再接收新的浏览器音频，但等待服务返回剩余最终结果。

## 7. 错误处理

- 麦克风权限被拒绝：前端显示浏览器权限操作建议，不建立后端会话。
- WebSocket 连接失败：显示本地服务不可用，不开始录音。
- API Key 缺失：后端在会话开始前返回 `missing_credentials`。
- 参数错误：后端返回 `invalid_configuration`，不创建 Recognition。
- 阿里云连接或识别失败：返回 `provider_error` 和可选 `requestId`，停止采集并允许重试。
- 浏览器意外断开：后端停止对应 Recognition，释放会话资源。
- 音频格式不匹配：后端拒绝非预期的开始参数；第一版不在后端猜测或自动修复格式。

## 8. 安全与隐私

- API Key 只存在于后端进程环境。
- 日志默认只记录会话状态、错误类别、时延和 `requestId`。
- 不记录原始音频、完整转写或患者身份信息。
- 原型仅监听本地开发地址；若以后部署，必须增加 HTTPS/WSS、身份认证、租户隔离和数据保留策略。

## 9. 测试与验收

### 9.1 自动测试

- Adapter：模拟 SDK 回调，验证 partial/final 映射、错误映射和停止行为。
- WebSocket：验证开始、音频、停止的顺序以及非法状态拒绝。
- 前端状态：验证录音状态机、临时结果替换、最终句子追加和错误恢复。
- PCM 转换：对固定输入验证输出为单声道 16 kHz PCM16，分片时长接近 100 ms。

### 9.2 手工验收

- 用户允许麦克风后可开始录音，并看到音量反馈。
- 普通话讲话时，页面在句子结束前显示临时结果，结束后生成最终句子。
- 停止后等待尾部结果完成，不丢失最后一句。
- API Key 缺失、拒绝麦克风和断开后端时均显示明确错误。
- API Key 不出现在浏览器源码、网络响应、控制台和应用日志中。
- 页面在桌面和窄屏下均可操作。

## 10. 非目标

- 电话/SIP 接入。
- 多用户并发、账户、租户和权限系统。
- 数据库、会话历史、原始录音存储和云端部署。
- 自动语言切换、说话人分离或翻译。
- LLM 回复和 TTS 播放。
- 生产级计费、审计和可观测性。
