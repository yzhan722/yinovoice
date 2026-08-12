# 太平洋口腔演示 Prompt 扩充（1–2 分钟）

## Goal

让浏览器实时语音演示可自然聊满约 1–2 分钟：地址/分院/营业时间、种植与正畸等项目说明、症状分诊引导、转人工指引；避免症状类问题被一句「抱歉无法回答」带过。

## Approach

方案 B：扩充 `DEMO_PACIFIC_DENTAL_TENANT_PROMPT`，并将演示默认 `ResponseProfile` 调整为 `balanced` + `max_spoken_sentences=4`。

## Boundaries

- 可做：项目科普、症状分诊提问（一次一问）、引导到店/热线。
- 不可做：确诊、开药、编造价格/排班/优惠、假装已预约。
- 急重症：引导急诊/急救，不继续闲聊。

## Delivery

- 改 `platform-api` 种子 Prompt + demo ResponseProfile。
- 重启 `yino-platform-api`（内存仓库启动时重载 demo）。
