# LiveKit 语音闭环与业务平台 Demo 设计

## 目标

以 `BaseVapiYinoai/ai-voice-management` 为前端功能基线，建立一个脱离 Vapi 核心依赖的可展示 Demo：

- 浏览器能够完成真实的 `语音输入 → STT → LLM → TTS → 语音输出` 闭环。
- 管理员端和诊所端保留现有全部业务模块。
- 核心配置、知识库、预约、回访任务、Web 会话和日志真实运行。
- 电话、计费和复杂统计在 Demo 阶段完整展示，但允许使用明确标记的演示数据。
- 后端采用版本化 API，后续可继续增加前端功能和替换模型供应商。
- 客户演示聚焦“能配置、能对话、能办业务、能查看结果”，不展示底层技术链路和诊断面板。

本设计覆盖完整平台 Demo。已批准的
`2026-07-31-livekit-local-voice-loop-design.md`
作为第一个技术里程碑继续有效。

## 现有平台盘点

现有平台为 Vue 3、Vite、TDesign、Pinia、Vue Router 和 ECharts 前端，共有管理员与用户两套动态菜单和独立 API Service。

### 当前启用模块

| 角色 | 模块 | 已有能力 |
|---|---|---|
| 管理员 | 登录 | 独立管理员登录、管理员信息 |
| 管理员 | 数据看板 | 用户数、Assistant 数、呼入、呼出、时长、趋势图 |
| 管理员 | 用户管理 | 创建、编辑、启停、删除、重置密码、头像、登录日志、操作日志 |
| 管理员 | AI 助手列表 | 搜索、同步、分配用户、详情、状态 |
| 管理员 | AI 助手详情 | 基本、Model、Voice、Transcriber、消息、服务器、高级配置 |
| 管理员 | Prompt | 管理员 Prompt 与用户 Prompt 分离 |
| 管理员 | Voice 字典 | Voice 查询、创建、编辑、删除 |
| 管理员 | 通话记录 | 搜索、同步、详情、录音、摘要、消息、成本和技术字段 |
| 管理员 | 知识库 | 上传、同步、状态、下载、查看关联 Assistant |
| 诊所用户 | 登录与资料 | 独立用户登录、用户资料 |
| 诊所用户 | 数据看板 | 当前用户呼入、呼出、时长和趋势 |
| 诊所用户 | 客服设置 | 选择 Assistant、用户 Prompt、Voice、欢迎语、结束语、转接号码 |
| 诊所用户 | 通话记录 | 当前用户记录、筛选、录音、摘要、消息 |
| 诊所用户 | 知识库 | 我的文件、授权文件、上传和下载 |

### 当前存在但未启用的模块

- 管理员和用户聊天历史页面。
- 管理员模型设置页面。
- Key 管理和 Dictionary API，但没有完整独立菜单。
- `webCall` 数据类型，但没有浏览器实时语音测试入口。

### 当前架构限制

- Assistant、通话和文件依赖 Vapi 同步接口。
- Assistant 主要从 Vapi 同步，缺少本平台原生创建、复制、草稿和发布流程。
- 前端没有真实 LiveKit Web Voice Playground。
- 没有工具管理页面，`toolIds` 只是配置字段。
- 没有预约、Webhook、知识检索测试或转人工工具的可视化配置。
- 管理员模型设置页面偏向直接暴露技术参数，不符合诊所用户只使用业务档位的原则。
- “用户”承担了诊所租户含义，缺少明确的 Tenant/Clinic 边界。
- 现有项目没有前端自动化测试脚本。

## 方案选择

采用“保留前端、替换服务层”的渐进方案：

```text
现有 Vue/TDesign 前端
        ↓
新的 /api/v1 平台 API
        ↓
Platform Control Plane
        ↓
LiveKit Agent Runtime
        ↓
STT / LLM / TTS / Tools
```

不从零重做前端，也不继续把 Vapi 数据模型作为内部核心模型。现有页面可以复用视觉和交互，但 API、字段命名和“同步 Vapi”的流程逐步改为平台原生操作。

## Demo 功能矩阵

### 必须真实运行

| 模块 | Demo 真实能力 |
|---|---|
| Web Voice Playground | 麦克风、扬声器、开始/结束会话、实时字幕、Agent 状态、基础打断、多轮对话 |
| Local Voice Probe | LiveKit `console` 模式本地 STT→LLM→TTS |
| Agent 管理 | 创建、编辑、启停、复制、分配诊所 |
| Agent 配置 | 业务档位、主要语言、Voice、欢迎语、结束语、用户 Prompt |
| Platform Prompt | 管理员可编辑；诊所端不可见、不可覆盖 |
| 配置生效 | 保存后新建会话读取最新已发布配置 |
| 知识库 | 文件上传、列表、状态、关联 Agent；至少 TXT 可被真实检索 |
| 知识问答测试 | 输入问题、查看命中文件与最终回答，验证知识是否生效 |
| 预约 | 在 Sandbox Calendar 中查询时间并创建演示预约 |
| 回访任务 | 创建、编辑、查看状态；不自动拨打真实电话 |
| Web 会话记录 | 保存消息、角色、时间、摘要和结束原因 |
| 角色模式 | 管理员和诊所端菜单与数据范围分离 |
| API | FastAPI `/api/v1` 和自动 OpenAPI 文档 |

### 使用演示数据但必须明确标记

| 模块 | Demo 表现 |
|---|---|
| 电话呼入/呼出 | 保留入口、状态和历史样例，标记“电话线路未连接” |
| 录音播放 | 使用随 Demo 附带的样例音频 |
| 电话成本 | 使用“估算/演示数据”标签 |
| 月度统计 | 基于 seed 数据与真实 Web 会话混合展示，并标明数据来源 |
| 运营商字段 | 展示预期字段，不发送真实电话 |
| 大规模并发和 SLA | 只展示目标，不宣称已经验证 |

### 本阶段不实现

- 真实 SIP 呼入、呼出和号码购买。
- 真实扣费、账单支付和套餐结算。
- 全球多区域部署和跨区域复制。
- 完整生产级向量数据库。
- 牙科诊所管理系统深度集成。
- 生产级 OAuth/SSO 和密码找回。
- 面向客户的 STT/LLM/TTS 分阶段时延、Provider 健康、fallback 和故障模拟面板。
- API 调试器、Prompt 拼接预览及其他以工程诊断为目的的页面。

## 必须保留的前端模块

### 管理员端

1. 数据看板。
2. 诊所/用户管理。
3. AI 客服列表。
4. AI 客服详情与分配。
5. 模型组合与 Voice 配置。
6. 管理员 Prompt 和诊所 Prompt。
7. 欢迎语、语音邮件、结束语和转接号码。
8. 通话/会话记录和详情。
9. 知识库。
10. 预约和回访任务。
11. Voice 字典。
12. 登录日志和操作日志。

### 诊所端

1. 数据看板。
2. AI 客服选择和设置。
3. 业务档位、Voice、诊所 Prompt 和消息设置。
4. Web 语音测试。
5. 通话/会话记录。
6. 我的知识文件与已授权文件。
7. 预约记录与回访任务。
8. 诊所资料和客服业务设置。

现有“同步 Assistant、同步通话、同步知识文件”按钮不再表示同步 Vapi。Demo 中分别替换为：

- 刷新平台 Agent 状态。
- 刷新会话索引。
- 重新处理知识文件。

## 新增业务模块

### 1. Web Voice Playground

这是当前平台最重要的缺失模块。

功能包括：

- 选择一个 Agent。
- 开始和结束浏览器语音会话。
- 麦克风权限和连接状态。
- 用户与 Agent 实时字幕。
- Listening、Thinking、Speaking 状态。
- 用户插话时停止当前播放。
- 会话结束后跳转到 Conversation Detail。

### 2. Agent 草稿与发布

配置编辑不能立即影响正在进行的会话：

- `Draft`：管理员或诊所正在编辑。
- `Published`：新会话使用的版本。
- `Disabled`：不可启动新会话。

Demo 只保留一个草稿和一个已发布版本，不实现复杂版本分支。

### 3. Business Profile

诊所用户不直接选择原始模型参数，只选择面向业务的档位：

- 中文标准。
- 江浙口音优化。
- 低延迟。
- 低成本。

管理员负责在后台将档位映射到 STT、LLM、TTS/Voice 和 fallback。客户演示页面不展示原始 Provider 参数。

### 4. 预约管理

诊所端可查看和管理：

- 患者姓名、联系方式和预约时间。
- 预约项目、备注和状态。
- 由语音会话创建的预约来源。
- Sandbox Calendar 中的空闲时间和预约结果。

Demo 不连接真实诊所日历，不向外部参与者发送通知。

### 5. 回访任务

诊所端可创建和查看回访任务：

- 患者、计划回访时间、回访原因和授权状态。
- 待处理、已完成、已取消状态。
- 示例回访摘要和满意度。
- “电话线路未连接”提示；Demo 不自动外呼。

### 6. Knowledge Test

知识库页面增加“测试检索”：

- 输入问题。
- 显示命中文件和片段。
- 显示最终回答引用的知识来源。

### 7. 创建 AI 客服向导

使用统一向导完成：

1. 选择诊所和客服用途。
2. 选择主要语言、业务档位和 Voice。
3. 设置欢迎语、结束语和诊所 Prompt。
4. 关联知识文件。
5. 启用预约或回访能力。
6. 保存草稿、发布并进入 Web 语音测试。

## 页面导航

### 管理员

```text
Dashboard
Clinics & Users
Voice Agents
Web Voice Test
Conversations
Knowledge
Appointments
Callback Tasks
Audit Logs
Telephony
Settings
```

### 诊所用户

```text
Dashboard
My Voice Agents
Test Agent
Conversations
Knowledge
Appointments
Callback Tasks
Settings
```

`Telephony` 在 Demo 中可以查看线路状态和预期配置，但必须显示“未连接真实线路”。

## 系统架构

```text
Vue 3 Frontend
  ├── REST /api/v1
  ├── WebSocket/SSE session events
  └── LiveKit Client SDK audio
              ↓
FastAPI Control Plane
  ├── Auth & role scope
  ├── Tenant/User API
  ├── Agent Config API
  ├── Session Token API
  ├── Knowledge API
  ├── Conversation API
  ├── Appointment API
  ├── Callback API
  └── Tool API
              ↓
LiveKit Agent Worker
  ├── Agent config loader
  ├── STT adapter
  ├── LLM adapter
  ├── TTS adapter
  ├── Knowledge retrieval
  └── Tool executor
```

### 数据存储

Demo 使用 SQLite 和本地文件目录：

- SQLite：用户、诊所、Agent、配置版本、会话、消息、摘要、预约、回访任务、工具结果、知识元数据。
- 文件目录：知识文件和样例录音。
- 进程内或轻量本地索引：TXT 知识检索。

Repository 层必须隔离 SQLite，后续可以替换 PostgreSQL 和正式对象存储。

## 核心领域对象

| 对象 | 说明 |
|---|---|
| Tenant | 诊所数据边界 |
| User | 平台管理员或诊所成员 |
| VoiceAgent | 诊所拥有的 AI 客服 |
| AgentConfigVersion | Draft/Published 配置 |
| BusinessProfile | 面向业务的模型组合 |
| KnowledgeFile | 诊所隔离的知识文件 |
| Conversation | Web 或 Phone 会话 |
| ConversationMessage | 用户、Agent 和工具消息 |
| Appointment | 语音会话或人工创建的 Sandbox 预约 |
| CallbackTask | 带患者授权状态的回访任务 |
| ToolDefinition | 平台批准的工具 |
| ToolBinding | Agent 启用的工具 |
| ProviderProfile | 管理员维护的供应商配置 |
| AuditEvent | 管理操作记录 |

Platform Prompt 属于平台配置，不作为 Tenant 可读字段返回。

## API 边界

所有平台接口从 `/api/v1` 开始。

```text
POST   /api/v1/auth/demo-login
GET    /api/v1/dashboard
GET    /api/v1/tenants
POST   /api/v1/tenants
GET    /api/v1/agents
POST   /api/v1/agents
GET    /api/v1/agents/{id}
PATCH  /api/v1/agents/{id}/draft
POST   /api/v1/agents/{id}/publish
POST   /api/v1/agents/{id}/duplicate
POST   /api/v1/sessions
GET    /api/v1/conversations
GET    /api/v1/conversations/{id}
POST   /api/v1/knowledge/files
POST   /api/v1/knowledge/search
GET    /api/v1/appointments
POST   /api/v1/appointments
PATCH  /api/v1/appointments/{id}
GET    /api/v1/callback-tasks
POST   /api/v1/callback-tasks
PATCH  /api/v1/callback-tasks/{id}
GET    /api/v1/tools
PATCH  /api/v1/agents/{id}/tools
```

浏览器音频仍通过 LiveKit Client SDK，不经过普通 REST 上传。实时字幕和 Agent 状态优先使用 LiveKit 数据事件；后台任务状态可以使用 SSE。

## Prompt 优先级

运行时顺序：

1. 代码强制的 Platform Policy。
2. 管理员维护、诊所不可见的 Platform Prompt。
3. 已发布 Agent Template 指令。
4. 诊所可编辑的 Tenant Prompt。
5. 当前会话上下文和检索知识。

前端 API 永远不返回 Platform Prompt 给诊所角色。

## Demo 数据标识

任何非真实运行数据必须携带：

```json
{
  "dataSource": "demo"
}
```

前端统一显示“演示数据”标签。真实 Web 会话使用：

```json
{
  "dataSource": "live"
}
```

不得把演示电话、成本或 SLA 数据表现成已经发生的真实业务结果。

## 错误处理

| 场景 | 前端行为 |
|---|---|
| 麦克风被拒绝 | 指引用户重新授权 |
| LiveKit 连接失败 | 保留配置页面，显示重试 |
| 模型组合未配置 | 禁止开始语音测试，并提示联系平台管理员 |
| 语音服务失败 | 显示“语音服务暂时不可用”并允许重试；技术细节只写入后台日志 |
| 知识处理失败 | 文件保留并允许重新处理 |
| 预约工具失败 | 不创建预约，保留对话并提示人工确认 |
| 回访任务缺少授权 | 禁止标记为可拨打，提示补充患者授权 |
| 无权限访问 Tenant 数据 | 返回 403，不仅依赖前端隐藏菜单 |
| 配置未发布 | Test 页面提示使用当前 Published 版本 |

## 测试策略

### 后端

- Tenant 数据隔离测试。
- Platform Prompt 不向诊所 API 泄漏。
- Agent Draft/Publish 测试。
- Session 创建读取 Published 配置。
- Knowledge 文件归属和检索测试。
- Conversation 与 Message 持久化测试。
- Appointment 和 Callback Task 的 Tenant 隔离与状态测试。
- 演示数据与真实数据标识测试。

### Agent

- Provider Factory 和配置测试。
- 中文 Agent 指令测试。
- 不发起真实请求的会话测试。
- Conversation event 记录测试。

### 前端

- 管理员和诊所菜单测试。
- Agent 编辑、保存和发布流程测试。
- Web Voice Test 的连接状态测试。
- 知识上传和检索测试。
- 预约创建与回访任务状态测试。
- Conversation 详情和演示数据标签测试。

### 手工演示验收

1. 管理员登录并看到完整平台导航。
2. 创建诊所用户并分配 Agent。
3. 配置 Platform Prompt、Business Profile、Voice 和欢迎语。
4. 发布 Agent。
5. 切换诊所用户，修改允许的 Tenant Prompt。
6. 上传 TXT 知识文件并完成检索测试。
7. 在浏览器开始语音会话，看到实时字幕和简洁状态。
8. 打断 Agent 说话并继续对话。
9. 通过对话查询知识并在 Sandbox Calendar 创建预约。
10. 会话结束后在 Conversations 查看消息、摘要和预约结果。
11. 创建一条已授权的患者回访任务并查看状态。
12. 查看带明确标签的电话、成本和 Dashboard 演示数据。

## 实施阶段

每个阶段分别形成实施计划和验收点。当前首先执行 Stage 1；上一阶段通过后再进入下一阶段，避免语音链路、平台后台和业务页面同时改动。

### Stage 1：本地语音闭环

完成独立 LiveKit Agents `console` 技术探针。

### Stage 2：Web 语音闭环

建立最小 FastAPI 会话入口，接入 LiveKit 浏览器音频、Session Token、实时字幕、简洁状态、打断和多轮会话。

### Stage 3：平台骨架与原生 API

复用现有 Vue 前端，建立 SQLite、Demo 登录、Tenant、Agent Draft/Publish、会话持久化和 seed 数据。

### Stage 4：业务配置与知识库

完成创建 AI 客服向导、业务档位、双层 Prompt、Voice、TXT 上传、Agent 关联和知识问答测试。

### Stage 5：预约、回访和完整展示

实现 Sandbox Calendar、回访任务、Dashboard、会话详情、演示数据标签、测试和客户展示脚本。

### Stage 6：电话 PoC（后续）

在前五阶段通过后，单独接入 LiveKit SIP 验证真实呼入和呼出，不阻塞本次 Demo。

## 成功边界

Demo 成功代表：

- 平台核心不再依赖 Vapi 才能完成 Web 语音会话。
- 管理员和诊所端完整模块可展示。
- 核心 Agent、Prompt、知识、预约、回访任务、会话和日志真实运行。
- 后续功能可以通过 `/api/v1` 模块化扩展。

Demo 不代表电话线路、生产安全、高并发、计费准确性或全球部署已经完成。
