# Stage1 Monorepo 隔离部署 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `yinovoice` monorepo（含 A1/A2）可部署到 `/opt/yino-vapi-stage1`，且新建表单带合成预填，验收时不为空壳。

**Architecture:** 以 `apps/` 为唯一部署真源；改写 `scripts/deploy_stage1_isolated.py` 适配 monorepo；前端以 `/stage1/` base 构建；Stage1 使用内存仓库；禁止写生产目录。

**Tech Stack:** Python (paramiko 部署脚本)、Vue 3 + Vite、FastAPI、systemd、nginx

## Global Constraints

- 主仓库：`E:\Repos\yinovoice`
- 目标：`/opt/yino-vapi-stage1` 与 `https://HOST/stage1/`
- 禁止覆盖 `/opt/yino-vapi`；禁止删除回滚备份
- 凭据仅 `BT_HOST` / `BT_USER` / `BT_PASSWORD`；不回显
- 未经用户明确说“提交”，不得 commit / push
- 新建表单预填仅为合成演示文案

---

### Task 1: 新建表单合成预填

**Files:**
- Modify: `apps/control-plane/web/src/pages/user/assistant-settings/InstanceCreateDialog.vue`
- Modify: `apps/control-plane/web/src/pages/user/assistant-settings/InstanceCreateDialog.test.ts`

**Interfaces:**
- Produces: 打开对话框时字段非空；提交仍调用既有 `createCustomerService`

- [x] **Step 1:** 更新测试：挂载后断言 display_name / organization_name / greeting / platform_prompt / tenant_prompt 均有非空默认值；原有提交与失败保留输入用例仍通过
- [x] **Step 2:** 在 `InstanceCreateDialog.vue` 的 `form` 初始值填入合成演示默认文案（中文，可编辑）
- [x] **Step 3:** 运行相关 vitest

### Task 2: 适配 Stage1 部署脚本到 monorepo

**Files:**
- Modify: `scripts/deploy_stage1_isolated.py`

**Interfaces:**
- Consumes: `apps/control-plane/api`、`apps/runtime/voice-agent`、`apps/control-plane/web/dist`
- Produces: 仅写入 `/opt/yino-vapi-stage1` 与 Stage1 systemd / nginx `/stage1` 片段

- [x] **Step 1:** 将 `LOCAL_*` 路径改为 monorepo 布局
- [x] **Step 2:** 删除恢复生产前端的逻辑
- [x] **Step 3:** 验收探测增加 Stage1 `GET .../customer-services`（列表）以及生产列表/新建仍 404
- [x] **Step 4:** 更新脚本顶部 docstring，说明源为 yinovoice apps/

### Task 3: Stage1 构建/部署说明与状态文档

**Files:**
- Create: `docs/platform/stage1-deploy.md`（或等价短文档，CMD 指令）
- Modify: `PROJECT_STATUS.md`
- Modify: `TASKS.md`
- Modify: design status already approved in spec

- [x] **Step 1:** 写 CMD：先用 Stage1 env 构建 web，再设 BT_* 运行部署脚本
- [x] **Step 2:** 更新状态：主仓库 yinovoice；生产未启用 A1/A2；Stage1 为验收通道
- [x] **Step 3:** TASKS 增加 Stage1 验收与“验收后再提交”

### Task 4: 本地构建 Stage1 前端并部署（需用户环境变量）

**Files:**
- 无源码变更（执行构建与部署）

- [x] **Step 1:** `pnpm build`（`VITE_BASE_URL=/stage1/`、`VITE_PLATFORM_API_BASE=/stage1`）
- [x] **Step 2:** 确认 `BT_PASSWORD` 等已在本机环境（不打印）
- [x] **Step 3:** 运行 `python scripts/deploy_stage1_isolated.py`
- [x] **Step 4:** 按 design 验收清单核对生产未被覆盖、Stage1 列表非 404

### Task 5: 提交门禁（仅当用户明确授权）

- [ ] **Step 1:** 用户确认 Stage1 冒烟通过后，再按批次 commit（本 plan 不自动执行）
