# 通话后报告层对接自家语音（分仓 + 契约）

日期：2026-08-25  
状态：已确认。实施计划：`docs/platform/superpowers/plans/2026-08-25-call-insights-channel-contract.md`  
仓库：

- 实时语音：`C:\Users\yino\Projects\yinovoice`
- 通话后报告（原 n8n 替代）：`C:\Users\yino\Projects\n8n-workflow-export\apps\vapi-call-insights`

本文件用白话写。不提交、不推送、不部署、不改现网 LucaPlus / INP 邮件。

## 一句话

电话可以打在 VAPI 上，也可以打在我们自己的语音（Yino）上。  
**分析报告那一层**继续是现在的 Insights，不要写死只能收 VAPI。  
两个仓库不合并。默认不发报告邮件；你手动把某个助手挂上，并且手动加了收件人，才发。

## 两个系统各干什么

```text
客人打电话
    │
    ├─ 打到 VAPI（现在的 LucaPlus / INP）
    │       → Insights 照旧收 webhook → 分析 → 按现有名单发邮件
    │
    └─ 打到 Yino（LiveKit / 以后 SIP）
            → Yino 自己完成通话、预约、回拨
            → 默认到此结束，Insights 不知道这场电话
            → 只有你手动挂上之后，Yino 才把「对话文本」告诉 Insights
            → Insights 可以分析；没加收件人就不发邮件
```

- **Yino**：实时通话、排期、预约。挂断必须成功，不能因为 Insights 挂了而失败。
- **Insights**：挂断之后的分析、HTML 报告、客户/质检邮件。不负责接听。
- **橱柜 / ERP / n8n 导出脚本**：不进这条线。

## 你要手动加什么（默认关掉）

新的 Yino 助手 **默认不接 Insights**。

要接上某一个助手，你自己做：

1. 在 Insights 里已有（或新建）一个客户名，例如 `inp-group`（和现在加 VAPI 客户一样，热加载，不发版）。
2. 在 Yino 这个助手上填写同一个客户名（`insights_profile`）。没填就不发送。
3. 若还要发邮件：再在 Insights 的收件人文件里给这个客户加 To/CC。没加就只分析、不发信。

没有「Yino 一上线就自动给所有通话发客户邮件」这条路。  
现网 LucaPlus / INP 不走这套绑定，继续只走 VAPI webhook。

## 挂断之后实际发生什么（Yino 已绑定的情况）

1. 客人挂断。Yino 先把通话存进自己的数据库（这一步必须成功）。
2. Yino 记下「回头告诉 Insights」：这场通话的编号、开始/结束时间、对话原文。
3. 后台慢慢 POST 到 Insights。失败就过一会儿再试。不回滚通话，不改预约。
4. Insights 认这个客户名，收下对话，排队做 DeepSeek 分析（和现在 VAPI 进线后一样）。
5. 只有该客户已经配置了收件人，才进入现在的邮件工人。否则到分析为止。

Insights 暂时不传录音地址（第一期 `recordingUrl` 为空），避免把内部存储路径送出去。

## 两边怎么对字段（给以后写代码用）

Yino 通话记录 → Insights 已有的一场 `Call`：

| 含义 | 从 Yino | 到 Insights |
|------|---------|-------------|
| 客户名 | 助手上的 `insights_profile` | URL 和 `profile` |
| 通话编号 | 通话 UUID | `callId` |
| 去重编号 | `yino` + 客户名 + 通话 UUID + 结束时间 的哈希 | `eventId`（重试同一条不会分析两次） |
| 开始/结束 | UTC 时间 | `startedAt` / `endedAt` |
| 时长 | 秒 | `durationSeconds` |
| 对话 | 按顺序拼成 `user:` / `assistant:` 行 | `transcript` |
| 摘要 | 第一期空着（预约意向仍留在 Yino） | `summary` |
| 录音 | 第一期不传 | `recordingUrl: null` |

对话原文和摘要必须至少有一个非空，否则 Insights 拒收。渠道标记为 `yino`，和 VAPI 进线分开，避免误走现网邮件规则以外的路径。

VAPI 现网接口 `POST /v1/vapi/:profile` **不改**。  
Insights 另开 `POST /v1/ingest/:profile` 专门收 Yino。口令单独一套，不和 VAPI webhook 口令混用。

## 出错时怎么办

| 情况 | 行为 |
|------|------|
| 助手没填客户名 | 不通知 Insights |
| Insights 客户名不存在 | 拒收；Yino 记下失败，等人改绑定 |
| Insights 暂时挂了 / 超时 | Yino 稍后重试；通话本身已成功 |
| 同一场通话重试多次 | Insights 视为重复，不再新建分析 |
| DeepSeek 分析失败 | 与现在相同：作业失败，不因此补发客户邮件 |
| 没配收件人 | 不建邮件任务 |

禁止：Insights 失败导致 Yino 挂断接口失败；禁止自动给未绑定助手发客户邮件；禁止把 LucaPlus / INP 切到这条新接口。

## 测试范围（写代码时必须覆盖）

Yino：

- 没填客户名：挂断成功，没有任何出站。
- 填了客户名：挂断成功，队列里有一条待发送；Insights 200 后不再重试。
- Insights 500：挂断仍然 200，队列会重试。
- 同一通话结束事件发两次：Insights 侧只分析一次。

Insights：

- 规范体收进后变成和 VAPI 一样的分析作业。
- 该客户没有收件人：有分析、无邮件任务。
- 手动加了收件人：才出现邮件任务（仍受现有 live/shadow/切流时间约束）。
- 未知客户名、缺对话、多余字段：4xx，不写通话。
- 现有 `POST /v1/vapi/lucaplus` 与 `inp-group` 测试全部保持绿色。

不测：把现网客户迁到 LiveKit、搬录音、并仓库、改 VAPI 助手 URL。

## 明确不做

- 合并 git 仓库
- 用 Insights 接听电话
- 用 Yino 重发 LucaPlus / INP 的客户报告
- 默认给所有 Yino 通话发邮件
- 第一期同步录音文件
- 自动创建 Insights 客户
