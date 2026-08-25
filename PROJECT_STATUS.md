# PROJECT_STATUS

## 2026-08-25 商业 MVP 入站电话闭环（代码已落地，未部署）

- **范围**：网页/会话后处理闭环优先：内建排期、Tool、挂断抽取、通知。电话 PSTN **暂缓**。
- **落点**：`apps/control-plane/api`、`apps/runtime/voice-agent`、`apps/control-plane/web`。未扩展 `deploy/src`。
- **SIP**：入站字段与 dry-run 脚本仍在；不接真实 trunk。网页 Demo 仍为 `web`。
- **排期**：Yino 内建单资源；`pending`/`confirmed` 占用；午餐用两段营业时间。不再编造「下个工作日上午」预约。
- **挂断抽取**：按时区解析「周五下午」等；无排期、无匹配项目或 `ensure_slot_available` 失败则写回拨。支持中国大陆手机与 `+614` 澳洲手机。
- **转接**：无实时转人工；只能 `create_callback`。
- **录音**：网页仍本地 blob；SIP Fake Egress 对象键仍保留。四项 S3 变量未配齐则关闭。
- **通知**：`SMTP_HOST` + `SMTP_FROM` 启用真实 smtplib（587 STARTTLS / 465 SSL）；失败记事件、不回滚业务写。排期页可保存租户通知邮箱。
- **租户**：Demo `X-Tenant-ID`。Alembic head：`20260824_0009`。
- **冒烟**：`scripts/smoke_commercial_mvp.py`（内存仓库）；手工清单 `docs/platform/2026-08-25-commercial-mvp-manual-checklist.md`。
- **未做**：真实 PSTN（Twilio 不能服务大陆 +86）、真实 Egress/S3 客户端、生产 RBAC、生产部署。Agent 未 commit / push。

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
