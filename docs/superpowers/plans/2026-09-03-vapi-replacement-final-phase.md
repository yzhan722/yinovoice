# Vapi 替代最终阶段开发计划

日期：2026-09-03  
状态：**执行中**（Phase 0 / Phase 1 已开工，见文末「进展记录」）  
目标仓库：`yzhan722/yinovoice` `main`  
服务器：阿里云雅加达（ap-southeast-5），LiveKit / Platform API / voice-agent / call-insights 同机部署

> **For agentic workers:** 本计划是唯一事实来源。每完成一项在文末「进展记录」追加一行并勾选任务；不要另起平行计划。涉及生产服务器的操作只允许在 Phase 2 / Phase 4 任务里明确列出的步骤中执行，且必须先有回滚方案。本文不得写入客户名称、租户邮箱、号码、密钥（仓库公开）。

## 1. 目标与完成定义

**目标**：Yino 平台完全替代 Vapi 后台与运行时。所有现存 Vapi 助手在 Yino 上以实例运行，全部 Twilio 号码经 LiveKit SIP 入站到 Yino，旧管理台（Vue 前端 + Spring Boot 后端 + MySQL）下线，Vapi 账户可停用。

**完成定义（全部满足才算完成）**

| # | 验收项 | 判定方式 |
|---|---|---|
| D1 | 每个租户用自己的账号登录新控制台，只看到自己的实例与全部历史通话（含 Vapi 时期） | 逐租户人工验收 + `test_admin_*` 自动化 |
| D2 | 6 个 Twilio 号码全部指向 LiveKit SIP，真实来电由 Yino 接听 | `LIVE_SIP_E2E_PASS`，每个号码至少 1 通真实通话有 `call_records` + 录音 + Insights 摘要 |
| D3 | 真人转接可用：客户要求人工时通话被转到租户配置的号码 | 真实通话 `ended_reason=transferred`，租户侧电话响铃 |
| D4 | 英文实例语音质量不低于现有栈 | 盲测：同一批脚本/录音，评审 ≥ 持平（见 P3.2 验收） |
| D5 | 旧管理台与 Java 后端停止运行，域名指向新前端 | `systemctl is-active spring_ai-voice-server-e` = inactive；nginx 站点切换 |
| D6 | Vapi 上无活跃号码与 webhook | Vapi 控制台核对；key 已轮换 |

## 2. 现状基线（2026-09-03 调研结论）

**Yino 已具备**：实例/双 Prompt/音色/发布回滚；网页实时语音（Qwen Realtime，中英）；通话会话生命周期 API 与挂断抽取（预约/回拨）；通话中 Tool（查档、建预约、建回拨）；内建单资源排期；电话号码绑定与 `X-Phone-Lookup-Token` 鉴权；LiveKit SIP 入站适配代码（模拟 E2E 通过，未真实拨号）；LiveKit Egress → S3 客户端（未配桶）；SMTP 通知；call-insights（已承接 Vapi 通道的通话后摘要/评分/邮件；Yino 通道代码完成未部署）；Release gate、运维 runbook；CI 五个 job 全绿。

**Vapi 侧在用能力**（只读盘点）：15 个助手（12 英 / 3 中，2 个承载 86% 生产流量）；6 个 Twilio 号码（5 个 +61、1 个 +1）；约 100 通/月全入站 PSTN；工具 14 个（真人转接/handoff 7、Google 日历 4、挂机 2、知识查询 1）；1 个中英 Squad；通话分析与全量录音。Google 日历与知识查询仅演示助手使用，**生产助手不依赖**。

**旧管理台**：Vue3 + TDesign 前端 + Spring Boot（Java 8）+ MySQL（8 表、17 MB：13 助手、815 通话、9 租户账号、1 管理员）+ Python 录音代理。Java 后端**只剩反编译代码**，不可维护。

**缺口**（按对完成定义的阻塞程度排序）

1. 多租户账号/角色与管理员控制台（阻塞 D1、D5）
2. PSTN 落地：`livekit-sip` 服务、Twilio SIP trunk、号码绑定（阻塞 D2）
3. 真人转接工具（阻塞 D3）
4. 按实例选择运行时档位 + 英文管线（Deepgram/ElevenLabs 插件）（阻塞 D4）
5. 数据迁移器（助手/通话/录音/租户）（阻塞 D1、D5）
6. 通话摘要回流与展示、SIP 录音存储（D2 质量项）
7. 工程基线：Postgres 进 CI、生产 Alembic 升 head、`-eng` 部署与主线合流、call-insights 重新部署（Phase 0）

## 3. 阶段与任务

### Phase 0 — 基线加固（1–2 天）

- [x] **P0.1 CI 覆盖 Postgres**：`api` job 增加 `postgres:17` service，单独一步以 `DATABASE_URL` 运行 `tests/test_db_migrations.py tests/test_postgres_*.py`；内存模式用例保持无 `DATABASE_URL`。
- [x] **P0.2 生产 Alembic 升到 head**（2026-09-06 完成，`20260825_0011` → `20260903_0013`）。用 `scripts/deploy_production_api.py`：仅后端（平台 API 源码 + 迁移 + 控制台密钥），**不动前端 dist 与承载实时通话的 voice-agent**，所有既有路由保持向后兼容。先备份源码与 `pg_dump`，再升级、写 `AUTH_SECRET` 与管理员引导（SFTP 写入，不经命令行），重启后核验。结果：路由 43 → 47、管理端点上线（无 token 401）、`demo` 旧账号仍可用且越权 403、数据完好（8 实例 / 3 通话）、**LiveKit token 签发 200 且 voice-agent 实际接受了任务派发**。回滚命令随脚本输出。
- [ ] **P0.3 部署 monorepo 版 call-insights** 到 `calls.yino.au`，替换旧独立仓库发布；平台 API 配置 `INSIGHTS_BASE_URL` / `INSIGHTS_INGEST_TOKEN`；为实例设置 `insights_profile`。
- [ ] **P0.4 `-eng` 部署合流**：英文实例改由 P3.2 的运行时档位承载，撤销独立 fork 部署。

### Phase 1 — 控制台接管（替代 dashboard.yinoai.com，Vapi 仍承载通话；约 3 周）

- [x] **P1.1 多租户账号与角色**（API）：新增 `users` 表（`tenants` 已存在）；角色 `platform_admin` / `tenant_operator`；密码 scrypt 哈希；登录支持多账号并兼容 demo 账号引导；token 增加 `uid` / `role`；管理员接口 `/api/v1/admin/tenants`、`/api/v1/admin/users`（列表/创建/禁用/重置密码）；`platform_admin` 可用 `X-Tenant-ID` 代表任一租户操作，`tenant_operator` 仍禁止越权。
- [x] **P1.2 跨租户搬移实例**（2026-09-06 完成；此前判断"按需即可"被现实推翻）：首次生产同步时本地已无租户映射文件，15 个助手全部落进 Demo 租户，于是搬移从"纠错工具"变成必需。迁移 `20260906_0014` 给 13 个租户维度外键加 `ON UPDATE CASCADE`（父子租户本就必须一致，这才是外键该有的语义），`POST /api/v1/admin/instances/{id}/assign` 因此只需一条 UPDATE，通话、转写、知识、排期、号码随实例迁移。**踩到的坑**：外键图有两层——`call_messages → call_records`、`appointments → service_offerings`，只改第一层会被第二层的 NO ACTION 挡住；重建约束还会丢掉原有的 `ON DELETE CASCADE`。两者都由 CI 的 Postgres 步骤发现并修正（本机无数据库，正是 P0.1 加的那步救了场）。
- [x] **P1.3 Web 管理员控制台**：`/user/platform-admin` 页面（租户列表与新建、操作员账号增删改与重置口令、启停）；菜单按 `meta.requiresRole` + `/auth/me` 返回的 `roles` 门控，租户操作员看不到该入口。**租户视角切换**：管理员可"进入租户视角"，此后所有租户页面（实例、通话、排期、知识库）都以该租户身份请求，页面顶部常驻提示条与"返回本租户"；`yinoHomeTenantId` 记录账号本租户，`yinoTenantId` 记录当前操作租户，租户操作员每次刷新都会被钉回自己的租户。未做：全局跨租户通话记录聚合视图（当前用视角切换逐租户查看）。
- [x] **P1.4 Vapi 导入器** `scripts/import_vapi.py`（映射逻辑在 `yino_platform_api.vapi_import`）：助手 `systemPrompt` → `tenant_prompt`（超 8000 字的余量写为知识条目、不 apply）、`firstMessage` → 欢迎语、音色按语言映射默认 CosyVoice（可用 `--voice-map` 覆盖）、Vapi 工具在报告中列出；通话 → `POST /call-records`（方向、转写、`ended_reason`、时长、主叫/被叫；隐藏号码置空）；录音下载后经 `POST /call-records/{id}/recording` 存储（录音存储新增 wav/mp3 支持）；租户/用户经 `/admin/*` 创建，初始口令写入报告；`--dry-run`、状态文件幂等。**发现**：Vapi `/call` 列表只保留约两周（53 通），815 条历史通话须从旧 MySQL 导出，脚本提供 `--legacy-calls-json`（`aac_*` 行，DATETIME 按 JDBC `GMT+11` 换算为 UTC）。真实账户 dry-run：15 个助手全部可映射（3 个提示词溢出、11 个含工具）。
- [x] **P1.5 过渡期同步（2026-09-06 完成，已止损）**：Vapi 只保留约 10 天的通话，**819 通历史里只有 43 通（5%）的录音还能取回，776 个已永久丢失**（转写与摘要因旧库同步而完整保留，只丢音频）。`scripts/sync_vapi_daily.py` + systemd `yino-vapi-sync.timer` 每天 03:20 拉取新通话与录音（`Persistent=true`，宕机后补跑；只走官方录音接口，因为存量 URL 已全部失效）。首跑：44 通通话、44 个录音、0 失败。切流完成后可停用。**注意**：首跑因本地已删除租户映射文件而把助手落进 Demo 租户，已由 P1.2 的 assign 接口具备纠正能力，正式归属见下方待办。
- **验收**：9 个租户账号在新控制台登录，各自看到自己的实例与全部历史通话；管理员能创建租户/用户并分配实例；旧 Java 后端可停机。

### Phase 2 — 电话接入（LiveKit SIP + Twilio；工程 1–2 周 + 线路开通周期）

- [ ] **P2.1 部署 `livekit-sip` + Redis**（雅加达同机），开放 5060/UDP 与 RTP 端口范围；LiveKit `livekit.yaml` 增加 `redis` 与 SIP 配置；systemd 单元与 runbook 写入 `docs/realtime/`。
- [ ] **P2.2 Twilio Elastic SIP Trunk → LiveKit SIP URI**；用 `integrations/sip/livekit/*.example.json` 与 `scripts/provision_livekit_sip.py` 创建 inbound trunk 与 dispatch rule（`hide_phone_number: true`）。
- [ ] **P2.3 平台配置**：`PHONE_LOOKUP_TOKEN`（API 与 runtime 一致）；6 个号码在「电话号码」页绑定到对应实例；runtime dispatch metadata 校验通过 `scripts/sip_preflight.py --probe`。
- [ ] **P2.4 `LIVE_SIP_E2E_PASS`**：先用测试号码真实拨打；核对 `call_records`（`direction=inbound`、主叫/被叫）、Insights 摘要、通话抽屉展示。
- [ ] **P2.5 SIP 录音**：部署 LiveKit Egress，OSS（S3 兼容）四项配置，验证 `recording_status=stored` 与网页回放。
- **验收**：测试号码真实来电 → Yino 接听 → 记录/录音/摘要齐全；voice-agent `release_gate --mode full` 仍 PASS。

### Phase 3 — 工具与运行时对齐（2–3 周）

- [ ] **P3.1 真人转接 `transfer_call`**：
  - API：实例增加 `forwarding_phone`（E.164）；`ToolName` 增加 `transfer_call`；`tool_invocations` 记录；`CallSessionFinish.ended_reason` 增加 `transferred`。
  - Runtime：`tool_protocol.ToolName` 增加 `transfer_call`；orchestrator 调用 `livekit.api.sip_service.transfer_sip_participant(room, sip_participant_identity, transfer_to="tel:+…")`（livekit-api 1.2.1 已提供）；转接前播报一句过渡语；失败回退为建回拨并继续对话；网页通道返回 `status=error`（不支持转接）。
  - Prompt：平台 Prompt 增加转接触发规则与标记示例。
  - 测试：runtime 用 fake SipService 覆盖成功/失败/非 SIP 通道；API 覆盖 `forwarding_phone` 缺失 → `status=error`。
- [x] **P3.2a 可插拔 LLM 供应商**（2026-09-06）：`llm_providers.py` 注册表让 pipeline 模式的 LLM 可选 OpenAI / DeepSeek / Qwen(DashScope 兼容模式) / Zhipu GLM / Moonshot Kimi / MiniMax / SiliconFlow / OpenRouter / 自建 OpenAI 兼容端点。全部走同一套 chat 协议，只有 endpoint、model、key 不同。`LLM_PROVIDER` 选型，`LLM_MODEL` / `LLM_BASE_URL` / `LLM_API_KEY` 可覆盖，各家也读自己的 key 变量以便并存；不设 `LLM_PROVIDER` 时行为与原先完全一致。TTS 仍用 `OPENAI_API_KEY`。
- [ ] **P3.2 按实例运行时档位与英文管线**：
  - 实例增加 `runtime_profile`（`qwen-realtime` 默认 / `pipeline-en`），API 在 LiveKit dispatch 时按档位选择 `agent_name`（每档位一个 worker 池，替代 `-eng` fork）。
  - Runtime pipeline 模式支持 `STT_PROVIDER=deepgram`、`TTS_PROVIDER=elevenlabs|openai`（`livekit-agents[deepgram,elevenlabs]` 插件），语言与音色来自实例配置；保留 Fun-ASR + OpenAI 组合。
  - 英文平台 Prompt 模板（现有模板为中文口腔场景）。
  - **验收（D4）**：用同一批英文脚本对 Qwen Realtime 英文与 pipeline-en 做盲测，评审打分；两个生产实例的档位按结果选定。
- [ ] **P3.3 通话摘要回流**：Insights 完成分析后回写 `call_records.summary` / `success`（或抽屉内嵌 Insights 结果），替代 Vapi `analysisPlan`。
- [ ] **P3.4 可选**：价目表 CSV 知识导入；Google 日历排期适配器（仅演示助手使用，默认暂缓）。

### Phase 4 — 切流与下线（1 周 + 观察期）

- [ ] **P4.1 逐号码切流**：Twilio 号码 Voice 配置从 Vapi 改为 SIP trunk；顺序：测试号码 → 中文助手 → 两个生产助手；每步观察 ≥ 3 个工作日；回滚 = 号码切回 Vapi。
- [ ] **P4.2 停用 Vapi webhook**（Insights 保留 Vapi 通道 30 天以便回滚）。
- [ ] **P4.3 数据终迁**：Vapi 录音全量拉取；MySQL 导出归档；停止 `spring_ai-voice-server-e` 与录音代理；`dashboard.yinoai.com` nginx 指向新前端 dist。
- [ ] **P4.4 Vapi 账户降级/关闭；轮换所有出现过的密钥**。

## 4. 工作量与排期（单人估算，可并行处）

| 阶段 | 工程量 | 外部依赖 |
|---|---|---|
| Phase 0 | 1–2 天 | 生产维护窗口 |
| Phase 1 | 已完成 P1.1 / P1.3 / P1.4；剩 P1.2（降级，按需）与 P1.5（可选） | 无 |
| Phase 2 | 1–2 周工程 | Twilio SIP trunk 开通、OSS 桶、端口放通 |
| Phase 3 | 2–3 周（P3.1 3–5 天、P3.2 7–10 天、P3.3 2 天） | Deepgram / ElevenLabs 账号；盲测评审人 |
| Phase 4 | 1 周 + 观察期 | 租户沟通窗口 |

Phase 1 与 Phase 2 可并行（前者纯代码，后者以运维为主）；Phase 3 依赖 Phase 2 的真实 SIP 通道做转接验收。乐观总周期约 6–8 周。

## 5. 风险与对策

| 风险 | 对策 |
|---|---|
| **Vapi 录音每天继续丢失**（保留期约 10 天） | P1.5 每日同步（已升级为必做）；尽快推进 Phase 2 切流，让新通话直接由 Yino 录音 |
| stage1 曾停在孤儿迁移版本 `20260818_0002` 而无法升级 | 已重建 stage1 库并升到 head；**教训**：迁移文件一旦发布不得改 revision id，生产库 `20260825_0011` 未受影响 |
| 英文语音质量不及现有栈 | P3.2 双档位并存，盲测后再切；生产助手最后切流，随时回滚号码 |
| `livekit-sip` / Egress 运维复杂度 | 同机部署 + systemd + runbook；`sip_preflight.py --probe` 纳入 release gate |
| 雅加达 ↔ 澳洲媒体时延 | 约 100 ms 量级可接受；切流后监控 `RuntimeMetrics` 首响与打断延迟 |
| 多租户改造破坏 `X-Tenant-ID` 兼容 | voice-agent 与测试保留 header 路径；仅 `platform_admin` 允许 header 覆盖 token 租户 |
| Vapi 录音 URL 私有/过期 | P1.4 迁移时立即用 API 下载落盘，不依赖 URL |
| Postgres 路径长期未被 CI 验证 | P0.1 已补；新增迁移必须带 Postgres 用例 |

## 6. 进展记录

- 2026-09-03 P0.1 完成：CI `api` job 增加 Postgres service 与独立测试步骤。
- 2026-09-03 P1.1 完成（API 侧）：`users` 表与迁移 `20260903_0013`、多账号登录、角色、管理员租户/用户接口、demo 账号引导播种、测试覆盖。Web 管理页留待 P1.3。
- 2026-09-03 P1.4 完成：`scripts/import_vapi.py` + `yino_platform_api.vapi_import`，9 个用例（含端到端导入、录音存储、幂等重跑、dry-run）；真实 Vapi 账户只读 dry-run 通过。录音存储支持 wav/mp3。英文运行时先用 Qwen（P3.2 盲测不过再切 OpenAI Realtime 或 Deepgram+ElevenLabs 管线）。
- 2026-09-06 stage1 测试库全流程演练通过（用户要求「先跑测试库」）：库因孤儿版本 `20260818_0002` 无法升级，备份后重建并升到 `20260903_0013`（20 表）；从旧 MySQL 生成租户映射（6 租户 / 8 助手映射 / 5 未分配归 Demo / 6 操作员）并导出 819 通历史通话；导入结果 15 助手→实例、819 通话、8240 条转写、43 个录音（93 MB，接口回放 200 + RIFF）、776 个录音状态 `none`；导入的操作员登录只见本租户，跨租户与管理接口 403。生产全程未受影响。
- 2026-09-06 P0.2 生产升级完成并验证（详见上）。**发现并修复**：导入器原先依赖旧库里的 `recordingUrl`，实测这些链接已全部失效（R2 预签名过期、`storage.vapi.ai` 域名不再解析），改为优先走 Vapi `GET /call/{id}/mono-recording`；dry-run 不再要求管理员 token。
- 2026-09-06 P3.2a 可插拔 LLM 供应商完成（详见上）。voice-agent 419 passed、release gate PASS。
- 2026-09-06 Vapi 三层复刻调研完成：见 `docs/realtime/vapi-stack-parity.md`。13 个助手中 10 个可 1:1 复刻（Deepgram nova-2/nova-3/flux 与 OpenAI gpt-4o-transcribe、GPT-4o/4.1、ElevenLabs eleven_turbo_v2_5/eleven_flash_v2_5 及其四项调参，LiveKit 插件参数名与模型名完全一致，音色 ID 可直接复用）；3 个用 Vapi 自有音色的需替换。落地 `stt_providers.py` / `tts_providers.py` 注册表，海外插件收在 `overseas` extra，不设 `*_PROVIDER` 时行为不变。voice-agent 438 passed。
- 2026-09-06 P1.5 每日同步上线并首跑成功（44 通 / 44 录音 / 0 失败），录音流失已止住。
- 2026-09-06 P1.2 完成（见上）。CI Postgres 步骤连续拦下两个只在真实数据库才暴露的错误：不存在的仓储方法、以及二层外键未级联。
- 2026-09-03 P1.3 完成：`/user/platform-admin` 页面 + `PlatformAdminService` + 角色菜单门控 + 租户视角切换；前端 99 passed、typecheck 干净。浏览器验收：以 `root` 登录 → 新建租户（ap-southeast）→ 建操作员 → 进入租户视角 → 导入 7 个行业演示落在新租户；接口复核：新租户 7 个实例、Demo 仍 1 个、操作员登录只见本租户、跨租户与管理接口均 403。P1.2 降级为按需纠错工具（理由见上）。**Phase 1 控制台接管的关键路径已完成**，旧 Java 后台在完成 P0.2/P0.3 与正式导入后即可下线。
