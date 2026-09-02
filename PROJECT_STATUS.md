# PROJECT_STATUS

## 2026-09-02 DEV-A Runtime hardening (synthetic)

- Voice Agent local suite **308 passed**. Concurrency 10/25/50, finish race matrix, Qwen malformed/unexpected events, barge-in, tool cancel, FakeClock soak (500 turns / 1000 `response.done`), replay + SIP synthetic fixtures, worker drain, recording seam.
- Usage is session-local deduped by Qwen `response.id`. Malformed events do not crash the agent. Tool non-idempotent names are still not retried.
- Latency numbers in `docs/realtime/runtime-hardening-results.md` are **SYNTHETIC**. Real calls tested: **0**. Status remains **NEEDS_LIVEKIT_PROVISIONING**, not `LIVE_SIP_E2E_PASS`.
- No new Control Plane / Call Insights work this campaign. API / Insights failures stay **OUT_OF_SCOPE_B**.

## 2026-09-01 DEV-A Egress / usage / lookup 鉴权

- LiveKit RoomComposite 音频 Egress 客户端已接控制面：S3 四件套 + LiveKit API 配齐后写入既有对象键；失败不挂断。CI 不连真实桶。
- Qwen `response.done` usage 累加后随 `/finish` 落 `call_records.usage`（Alembic `20260901_0012`）。日志只记 response_count / total_tokens。
- `GET /api/v1/phone-numbers/lookup` 必须 `X-Phone-Lookup-Token`；空 `PHONE_LOOKUP_TOKEN` 一律 401。Runtime 未配置 token 则根本不发查询。
- 详见 `docs/realtime/2026-09-01-egress-usage-lookup-auth.md`。未覆盖生产、未配真实 S3。

## 2026-09-01 DEV-A 国内 SIP 送号归一化

- Runtime 接受常州固话 `0519…`、京号 `010…`、400 与 11 位手机等国内送号，收成 E.164 后再 `phone-numbers/lookup`。非号码字符串仍 fail closed。
- 电信 IP 白名单中继模板：`integrations/sip/livekit/inbound-trunk.ip-acl.example.json`。
- 仍未买号、未改 trunk、未拨打。

## 2026-09-01 多行业演示已覆盖生产网页

- 已覆盖 `/opt/yino-vapi` 的 frontend-dist 与 platform-api/src；**未改** `config/*.env`；**未动** Stage1。备份 `*.bak-20260901-202623`。
- API 重启后 Demo 租户已有 8 个实例（7 个行业合成演示 + 原口腔实例）。`POST /industry-demos` 回 `created:0 skipped:7`（幂等）。front 200，Stage1 仍为 active。
- 入口：`https://8.215.80.82/#/user/realtime-voice`，请硬刷新后再切实例。

## 2026-09-01 多行业合成演示案例

- 7 个虚构行业实例（口腔、餐饮、酒店、美业、教培、汽车售后、房产看房）：完整前台话术、预约/回拨 Tool、排期项目、知识条目。
- Demo 租户 API 启动时幂等补齐；网页「我的实例」可点「导入行业演示」。试话见 `docs/platform/2026-09-01-industry-demo-scenarios.md`。
- 挂断抽取补了订桌/订房/试听/看房/保养等意向词。现站需覆盖 API + 前端后才会出现。

## 2026-09-01 实时语音页可切换多实例

- 实时语音页列出当前租户全部语音实例；下拉切换会结束当前通话、按新 `customer-service-id` 重挂 LiveKit 面板，并写入 `yino-selected-instance-id` 与 `?instanceId=`。
- 「我的实例」增加「开始通话」，进入实时语音页时带上该实例。
- 实时语音页可直接选 CosyVoice 音色；保存到当前实例后重挂面板，下次开口生效。

## 2026-09-01 生产 `/opt/yino-vapi` 覆盖（用户明确要求网页通话，非本机）

- 已覆盖宝塔现站 `https://8.215.80.82/`：frontend-dist + platform-api + voice-agent 源码；**未改** `config/*.env` 里的密钥；**未动** `/opt/yino-vapi-stage1`。
- 生产库 `yino_platform` 已从 Alembic `20260811_0001` 升到 `20260825_0011`。备份目录带时间戳 `*.bak-20260901-173811`。
- 验收（本机 SSH 回环）：front 200、`/health` 200、`GET /api/v1/customer-services` 200（覆盖前 list 为 404）。LiveKit / API / voice-agent systemd 均为 active。
- 网页通话入口：`https://8.215.80.82/#/user/realtime-voice`（浏览器麦克风，不是手机号）。

## 2026-09-01 DEV-A Live SIP Stage E2E（本机）

- 代码门仍是 **READY_FOR_LIVE_SIP_TEST**。真电话门：**BLOCKED** / **NEEDS_LIVEKIT_PROVISIONING**。
- 本机无 `.env.local`、无 `LIVEKIT_*` / `PLATFORM_API_URL`、无运行中的 voice-agent、无 :7880 / :8000。`sip_preflight.py --probe` 因凭据缺失跳过。
- 未买号、未改 trunk/dispatch、未拨打。结果：`docs/realtime/2026-09-01-live-sip-e2e-result.md`。

## 2026-09-01 DEV-A LiveKit SIP inbound（代码在 `feat/a-runtime-finish-once`，未 commit / 未部署 / 未真实拨号）

- Runtime 可从 LiveKit SIP participant attributes 解析 inbound call，经 `GET /api/v1/phone-numbers/lookup` 解析 tenant/agent，再进入既有 `create_dispatched_runtime` / lifecycle / exactly-once finish。
- 生产 empty-metadata 任务只等待 SIP kind；lookup 超时不把 callee URL 链进异常；日志对 `sip.callID` 做号码脱敏。Dispatch 模板默认 `hide_phone_number: true`。
- Fake Telephony seam 保留；生产路径不使用 `FakeInboundProvider._seen_ids`。
- 未购买号码、未修改 LiveKit trunk/dispatch、未拨打真实电话。Stage 模板：`integrations/sip/livekit/`。Runbook：`docs/realtime/2026-09-01-sip-inbound-stage-runbook.md`。

## 2026-08-31 Call Insights Monorepo（代码在 `feat/b-monorepo-insights`，未 commit / 未部署）

- **合仓**：`apps/vapi-call-insights`（来源仓 `yzhan722/vapi-call-insights` @ `762eeb2`）以 Git 跟踪内容迁入 `apps/call-insights`。未迁 n8n export 工具、无嵌套 `.git`、无真实 `.env`/DB/音频。
- **运行时边界未改**：`POST /v1/vapi/:profile` 与 `POST /v1/ingest/:profile` 保持；独立 `INGEST_AUTH_TOKEN`；Yino `channel=yino` 默认不建邮件 Outbox；`mailEnabled=true` 才 opt-in；`recordingUrl` 仍为 null。
- **共享契约**：`packages/contracts/ended-call`（schema + fixtures）；API 与 Insights 测试绑定同一 fixtures。
- **CI / 本地入口**：`.github/workflows/ci.yml`；`scripts/test_all.ps1`。
- **分支**：本工作树在 `feat/b-monorepo-insights`（跟踪 `origin/dev/platform-insights`）。Agent 未 commit、未 push、未部署。旧仓未删除。
- **已知基线**：本机全新安装 `apps/runtime/voice-agent` 时，`livekit-agents` 解析到 1.7.1，有 6 个既有 realtime 测试失败。DEV-B 不修改 voice-agent 测试或依赖以迎合 CI。

## 2026-08-25 Call Insights 渠道契约（代码已落地，未部署）

- **Insights**（独立仓 `n8n-workflow-export/apps/vapi-call-insights`）：`POST /v1/ingest/:profile` + `INGEST_AUTH_TOKEN`；`Call.channel` 为 `vapi|yino`；yino 默认不建邮件 outbox。VAPI 路由与 lucaplus/inp-group 收件人文件未改。
- **Yino**：实例可空 `insights_profile`；Alembic `20260825_0010` 队列表；`finish` 后入队；后台 `INSIGHTS_BASE_URL` + `INSIGHTS_INGEST_TOKEN` 才 drain。缺绑定或空对话不投递。
- **未做**：生产部署、Vue 绑定表单、录音 URL、自动创建 Insights 客户、把 LucaPlus/INP 切到 ingest。
- **Runtime finish**：派发会话在 `session.start` 之后等到 LiveKit `close`（或 job shutdown）再 `POST /finish`；异常仍记 `failed`/`agent_error`。无 close 钩子的测试会话在 start 后立即 finish。
- Agent 未 commit / push。

## 2026-08-25 租户登录 / 配置发布 / 知识 SoT（代码已落地，未部署）

- **登录**：`POST /api/v1/auth/login` 发 HMAC token；`GET /api/v1/auth/me`。默认账号 `demo` / `demo123`，租户绑定 Demo UUID。Web：`VITE_SHELL_MOCK=false` 走 Platform；mock 仍可进壳，但会写入同一 Demo 租户。
- **租户解析**：Bearer 有效则用 token 内租户；仅 `X-Tenant-ID` 仍给测试与 voice-agent；两者都有且不一致 → 403；都没有 → 401。
- **配置发布**：创建实例自动基线快照；`GET .../revisions`、`GET .../config-diff`、`POST .../publish`、`POST .../rollback`。通话仍读当前实例行，不拆 draft/live 调度。
- **知识**：文本条目挂在实例上；`POST .../knowledge/apply` 写入 `tenant_prompt` 的 `<!-- yino-knowledge-start -->` / `end` 标记。仅 `.txt`；无 PDF/DOCX/RAG。
- **Alembic head**：`20260901_0012`（`call_records.usage` JSONB）。修订自 `20260825_0011`。
- **未做**：SSO、角色矩阵、计费、真实 PSTN、生产 S3/Egress worker、通话中 RAG。

## 2026-08-25 商业 MVP 入站电话闭环（代码已落地，未部署）

- **范围**：网页/会话后处理闭环优先：内建排期、Tool、挂断抽取、通知。电话 PSTN **暂缓**。
- **落点**：`apps/control-plane/api`、`apps/runtime/voice-agent`、`apps/control-plane/web`。未扩展 `deploy/src`。
- **SIP**：入站字段与 dry-run 脚本仍在；不接真实 trunk。网页 Demo 仍为 `web`。
- **排期**：Yino 内建单资源；`pending`/`confirmed` 占用；午餐用两段营业时间。不再编造「下个工作日上午」预约。
- **挂断抽取**：按时区解析「周五下午」等；无排期、无匹配项目或 `ensure_slot_available` 失败则写回拨。支持中国大陆手机与 `+614` 澳洲手机。
- **转接**：无实时转人工；只能 `create_callback`。
- **录音**：网页仍本地 blob；SIP Fake Egress 对象键仍保留。四项 S3 变量未配齐则关闭。
- **通知**：`SMTP_HOST` + `SMTP_FROM` 启用真实 smtplib（587 STARTTLS / 465 SSL）；失败记事件、不回滚业务写。排期页可保存租户通知邮箱。
- **租户**：Demo 操作员 HMAC + 兼容 `X-Tenant-ID`。Alembic head：`20260825_0011`。
- **冒烟**：`scripts/smoke_commercial_mvp.py`（内存仓库）；手工清单 `docs/platform/2026-08-25-commercial-mvp-manual-checklist.md`。
- **未做**：真实 PSTN（Twilio 不能服务大陆 +86）、真实 Egress/S3 客户端、SSO/角色矩阵/计费、生产部署。Agent 未 commit / push。

## 2026-08-13 主仓库与部署边界

- **新主仓库**：`E:\Repos\yinovoice`（`yzhan722/yinovoice`）。旧 `YinoVoicePlatform` 仅对照，不覆盖新仓。
- **生产** `https://8.215.80.82/`（`/opt/yino-vapi`）：已回滚到 A1/A2 之前；`GET/POST /api/v1/customer-services` 为 404；不得擅自再部署 A1/A2。
- **Stage1 验收通道**：`/opt/yino-vapi-stage1` + `https://HOST/stage1/`；部署真源为 `apps/`；说明见 `docs/platform/stage1-deploy.md`。
- **2026-08-13 Stage1 已部署**：stage 首页 200；`GET /stage1/api/v1/customer-services` 200；生产列表/新建仍 404；生产与 Stage1 systemd 均 active；回滚备份仍在。
- **Stage1 数据库**：共用 Docker `yino-platform-postgres`，独立库 `yino_platform_stage1`（含 instances / call_records / call_messages 等表）。已冒烟：创建实例与通话记录后重启 API 仍可读取；生产库计数未变。
- **通话记录 CRUD（软删除）**：已落地 `deleted_at` 迁移、`PUT`/`DELETE`/`restore`、网页删改；Stage1 已部署并 API 冒烟通过。生产未启用该能力。
- A1/A2、Stage1 部署脚本、通话记录软删除 CRUD 与迁移治理文档均在本地工作区，**待用户自行 commit / push**（Agent 未自动提交）。

## 2026-08-13 功能进展：Voice Agent Instance A2

- 已新增租户隔离的 `POST /api/v1/customer-services`；实例 UUID、租户和初始版本由服务端控制。
- “我的实例”页面已加入新建表单，支持名称、机构、欢迎语、音色及双 Prompt；成功后进入新实例配置页。
- 新建表单打开时预填合成演示默认值（名称/机构/欢迎语/双 Prompt），避免创建空壳实例；用户仍可修改。
- 列表加载错误现在与“暂无实例”明确区分。
- 已提供只允许 `local` / `test` 且需显式开关的四条合成演示实例幂等初始化函数。
- 未发现可安全确认的本地/测试数据库连接，因此本轮没有执行数据库写入；用户可直接通过网页新建，或在安全测试数据库接入后调用初始化函数。
- 本阶段仍未实现删除、停用或恢复实例。

## 2026-08-13 功能进展：Voice Agent Instance A1

- 已新增租户隔离的 `GET /api/v1/customer-services` 列表接口，支持 `limit` / `offset` 分页。
- Control Plane Web 的助手列表、实时通话与知识库配置已统一使用真实 UUID，不再依赖固定 Demo 实例 ID。
- 实例选择顺序为：URL 查询参数、当前浏览器会话已选实例、租户列表首项；失效选择会安全回退。
- 已复用知识库配置页作为实例配置入口，现有 `GET/PUT /customer-services/{id}` 编辑能力保持不变。
- 本阶段未加入实例新建、删除、停用，也未加入通话删除、租户管理、预约或回拨数据表。
- 验证：API `71 passed, 12 skipped`；Web `71 passed`；前端类型检查和生产构建通过。PostgreSQL 集成测试因未配置测试数据库而跳过。

更新日期：2026-08-13

## 总览

| 项 | 状态 |
|----|------|
| 目标仓库 | `yzhan722/yinovoice` |
| 本地克隆 | `E:\Repos\yinovoice` |
| 远程内容（整理前） | 空仓库 |
| 本轮动作 | 已从本机/LAN **复制整理**并完成治理文档标准化（源项目未改、未嵌套 `.git`） |
| 本地 Git | `main` 已有迁移提交 `d88ee92`；本轮 Codex 未 commit |
| 远程 Git | 复核时 `git ls-remote origin` 未返回分支；不得假定本地提交已推送 |

## 已纳入

- Control Plane API / Web / Runtime voice-agent（来自 stage1 worktree）  
- 根文档 `CONTEXT.md`、`docs/source-root`、`docs/platform`  
- LAN：`packages/platform-core`、`deploy/`、`integrations/`（已排除疑似正式 `.env` 与前端构建产物）  
- 协作文件：`README` / `AGENTS` / `SECURITY` / 等  

## 本轮未纳入（默认）

- `archive/` 原型（STT hello、fun-asr、web-console、ai-voice-management）  
- `livekit-server.exe`  
- 任何通话录音、真实 `.env`  
- 原 Git 历史（未做 subtree/历史合并）  

## 已知限制

- `scripts/` 部分路径可能仍假设旧目录名 `YinoVoicePlatform`  
- `deploy/` 含历史部署快照，需后续与 `apps/` 去重收敛  
- `deploy/src` 与 `apps/` 存在代码快照重复，本轮按“不删除文件”保留
- 已跟踪三个 `*.egg-info` 生成元数据目录；本轮仅补充忽略规则，是否移除需单独确认
- 当前协作者的 Git 凭据具备仓库读写权限，但 GitHub Desktop 登录账号仍需在界面人工确认
- 当前账号无法读取 rulesets；是否强制 PR 需由仓库所有者或管理员核验

## 当前验收状态

- 目录和治理文件已纳入目标仓库。
- 未发现嵌套 `.git`、submodule、音频、真实 `.env`、数据库备份或超过 50 MB 的文件。
- 敏感信息扫描仅发现测试、示例、开发配置和代码变量候选；没有确认的真实密钥。自动扫描不能替代提交前人工检查。
- 测试、静态检查和类型检查结果见 `docs/migration/最终验收报告.md`。
