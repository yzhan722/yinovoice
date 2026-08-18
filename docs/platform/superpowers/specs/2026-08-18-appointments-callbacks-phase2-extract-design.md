# C Phase 2：通话结束意向抽取设计

日期：2026-08-18  
状态：已部署 Stage1 可验收；不上生产  
范围：Control Plane；先 Stage1；不上生产  
仓库：`E:\Repos\yinovoice`  
前置：`2026-08-17-appointments-callbacks-phase1-design.md`  
约束：Qwen Realtime **无原生 Function Tool** → 采用通话结束抽取

## 目标

通话结束后，根据最终转写自动写入：

- 预约意向 → `appointments`（`source=voice_tool`）
- 回拨意向 / 信息不全 → `callback_tasks`（`source=voice_tool`）

网页预约/回拨列表可见；幂等（同一 `call_record_id` 不重复建）。

## 非目标

- Qwen / LiveKit 原生 Tool 调用  
- 通话中实时旁路写入  
- 真外呼、Google Calendar、完整排班冲突  
- 外部大模型抽取（本期用规则 + 结构化启发式，可测、无密钥依赖）

## 流程

```
通话结束 → POST/PUT call-records（含 messages）
         → 同步调用 extract_intents(record)
         → 规则解析转写
         → 写 appointment 和/或 callback（或都不写）
```

触发点：

1. `POST /api/v1/call-records` 成功且 `messages` 非空  
2. `PUT /api/v1/call-records/{id}` 更新 messages/status 后（幂等）  
3. 显式 `POST /api/v1/call-records/{id}/extract-intents`（验收/补跑）

软删通话：不抽取；已抽过则跳过。

## 抽取规则（启发式）— 方案 A 已放宽

拼接 user/assistant 文本后检测：

| 信号 | 行为 |
|------|------|
| 含预约类词（预约/想约/挂号/约个…） | **建 appointment**（缺电话/时段也写，notes 标待确认） |
| 缺电话 | `phone=待确认电话` |
| 缺时段 | 默认下一工作日 10:00–10:30，notes 标明占位 |
| 仅回电/回拨等、无预约词 | 建 `callback` |
| 无明显意向 | 不写 |

补充说明：`docs/platform/superpowers/specs/2026-08-18-appointments-auto-record-clarity-design.md`

## API

### `POST /api/v1/call-records/{id}/extract-intents`

- 200 + `{ appointment_id, callback_task_id, skipped_reason }`（未建则为 null）  
- 404：无记录或已软删  
- 幂等：若该 `call_record_id` 已有关联预约或回拨，返回已有 id，不新建  

自动触发失败不阻断通话记录保存（记日志；显式接口可重试）。

## Prompt 调整

`DEMO_PACIFIC_PLATFORM_PROMPT`：允许登记意向；**优先询问称呼/姓名**（便于回拨），再问电话/项目/时段；禁止宣称已约成功。不做真实医生档期校验。

## 后续（不做于本期）

真实预约系统：指定医生、项目时长、档期冲突判断、排班日历等——另开 Phase。

## 前端

预约列表：`source=voice_tool` 显示「语音自动」；展示 notes；可跳转关联通话。

## 验证

- 单测：样例转写 → 预约 / 回拨 / 跳过 / 幂等  
- Stage1（另授）：含「想约周五洁牙」的通话 → extract → 预约或回拨页可见  

## 明确不做

- 真 Tool 链路  
- 生产部署（另授）  
