# 商业 MVP 手工冒烟清单（合成数据）

更新日期：2026-08-25

本清单对应入站电话闭环 A–E。全程使用合成号码与假名，禁止真实客户/患者数据与录音。不部署生产。

自动化等价路径：

```cmd
cd /d C:\Users\yino\Projects\yinovoice
apps\control-plane\api\.venv\Scripts\python.exe scripts\smoke_commercial_mvp.py
```

该脚本走内存仓库，不访问 LiveKit / SMTP / S3。

## A. 号码映射

1. 租户页「电话号码」绑定合成 E.164（例如 `+61400000001`）到现有实例。
2. `GET /api/v1/phone-numbers/lookup?number=+61400000001` 须带 `X-Phone-Lookup-Token`，返回同一租户与实例。缺 token 为 401。
3. 重复绑定同一号码应 409。

## B. 入站会话生命周期

1. `POST /api/v1/call-sessions/start`，`direction=inbound`，`channel` 仅出现在 LiveKit metadata（值为 `sip`），落库方向为 `inbound`。
2. 追加 final 消息后 `finish`，状态离开 `in_progress`。
3. 通话抽屉显示入站、主叫/被叫；网页录音仍走本地 blob。SIP 在配齐 `RECORDING_S3_*` 与 LiveKit API 后走 RoomComposite → S3（OGG 对象键）；未配齐则 `recording_status=none`。

## C. 排期与预约

1. 「排期设置」保存 Melbourne 时区与工作日 09:00–12:00 / 13:00–17:00。
2. 新建服务项目后查询 `/availability`：午休无槽；占用后 409。
3. 不完整时段不得再编造「下个工作日上午」预约；应走回拨。挂断抽取仅在排期项目匹配且档期可用时写预约。

## D. 通话中 Tool

1. 助手最后一行 `[[tool:...]]` 由 Runtime 剥离后再写入 `call-sessions` 消息。
2. `POST /api/v1/tool-invocations` 业务失败返回 HTTP 200 且 `status=error`。
3. 同一 `idempotency_key` 写工具成功可重放；挂断抽取 `skipped_reason=tool_already_wrote`。

## E. Dashboard 与通知

1. 工作台 KPI 来自 `GET /api/v1/dashboard/summary`，无通话时接通率为 0，无编造待办。
2. 配置 `notification-settings` 合成邮箱（排期页「预约通知」）。未配 SMTP 时不发送；配齐 host+from 时走 smtplib，失败记事件且不回滚业务。
3. 未配齐四项 S3 变量时录音 Egress 关闭；配齐后仍是 Fake sink（不是真实 LiveKit Egress 客户端）。

## 仍属运维/后续

- 真实 PSTN trunk（已搁置）、真实 LiveKit Egress、生产 RBAC。
- 未授权不得 commit / push / 部署。
