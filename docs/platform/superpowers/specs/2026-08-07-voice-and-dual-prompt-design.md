# 音色切换与双层 Prompt 编辑

## Goal

1. 用户可切换客服 TTS 音色（Qwen Realtime 系统音色）。
2. Prompt 分两块：底层逻辑（管理员可编辑）+ 业务知识（用户可编辑）；用户页底层全文只读；两端均有「编辑 / 保存 / 取消」。

## Data model

- `CustomerServiceInstance.platform_prompt: str`（管理员维护；合成进 instructions）
- `CustomerServiceInstance.tenant_prompt: str`（用户维护）
- `VoiceProfile.tts_voice`: Qwen Realtime 系统音色 + 扩展库（含龙小夏/龙安温/龙安莉：`longxiaoxia`/`longanwen`/`longanli`）
- 演示种子：现有太平洋业务文案放入 `tenant_prompt`；对话规则/项目说明框架可放入 `platform_prompt`（或保留平台硬编码红线 + `platform_prompt` 话术层）

## Runtime

- voice-agent：`settings.qwen_realtime_voice` 作默认；实例 `tts_voice` 优先。
- 合成顺序：平台硬编码红线 → `platform_prompt` → 边界声明 → `tenant_prompt`（租户不可覆盖红线）。

## UI

- 用户知识库：音色下拉；底层 Prompt 全文只读；业务 Prompt 默认只读，编辑→保存/取消。
- 管理员知识库：底层 Prompt 编辑/保存/取消；可同步改音色（可选）。

## Auth（本期）

- Front `/admin/*` vs `/user/*` 路由隔离；API 仍按 `X-Tenant-ID`（与现网一致）。管理员页只给 admin 路由。
