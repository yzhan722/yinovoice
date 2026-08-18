# C Phase 2 补充：预约自动登记更具体（方案 A）

日期：2026-08-18  
状态：已部署 Stage1 可验收；不上生产  
前置：`2026-08-18-appointments-callbacks-phase2-extract-design.md`

## 目标

语音结束后，有预约意向时**优先写入预约表**；预约列表能清楚看出「语音自动」及待确认项。

## 抽取（放宽）

| 信号 | 行为 |
|------|------|
| 预约类词 | **始终建 appointment**（不再因缺电话/时段降级回拨） |
| 缺电话 | `phone=待确认电话`，notes 标明 |
| 缺时段 | 默认「下一工作日 10:00–10:30」UTC 占位，notes 标明时段待确认 |
| 仅回电词、无预约词 | callback |
| 无意向 | 不写 |

`notes`：`语音自动登记意向` + 待确认项 + 转写摘要（截断）。

## 列表 UI

- `source=voice_tool` → 「语音自动」标签  
- 展示 notes  
- 有 `call_record_id` → 「查看通话」→ `/user/call-history/detail/:id`

## 非目标

表结构不变；不上生产。
