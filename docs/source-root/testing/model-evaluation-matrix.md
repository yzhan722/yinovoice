# 模型统一评估矩阵

## 1. 目的

本模板用于比较 Transcriber、Model 和 Voice。它不允许把不同数据集、不同音频格式或不同时间获得的厂商数字直接排序。

## 2. 证据等级

| 等级 | 含义 | 可支持的结论 |
|---|---|---|
| A | 在冻结的自有电话测试集上、由统一框架实测 | Demo 场景下的候选排序 |
| B | 团队在许可清晰的公开数据集上复现实测 | 对指定公开数据集的初步排序 |
| C | 厂商官方文档、区域表、价格表或 API schema | 功能存在、区域可用和标价确认 |
| D | 无法复现的宣传材料或不可比厂商基准 | 仅用于发现候选，不进入评分 |

任何结果必须同时记录证据等级。没有 API Key 时，商业模型的所有性能指标均标记为 `not_run`，不能用 C/D 级证据填充 A 级单元格。

## 3. 统一运行条件

- 数据集版本与内容哈希固定；
- 单声道 8 kHz 电话音质为主测试，原始高保真音频仅作诊断对照；
- 按 `zh-CN`、`en-AU`、`en-US`、`en-GB` 分层报告；
- 同一候选至少运行三轮，保存请求区域、模型版本、时间和并发数；
- 当前 Demo 只运行 `CN_ALLOWED` 候选，并保存实际 API Endpoint、处理区域和区域准入证据；
- 故障测试只允许降级到另一个 `CN_ALLOWED` 配置，不得自动调用境外端点；
- 热词和 contextual biasing 使用相同 Domain Pack；
- 超时、限流、空结果和连接失败都计入可靠性，不从样本中删除；
- 成本同时记录厂商账单单位和折算的每通话分钟成本。

## 4. Transcriber 结果表

| 字段 | 类型 | 说明 |
|---|---|---|
| Provider / Model / Region | 标识 | 精确到 API 模型版本与调用区域 |
| Endpoint / Region eligibility | 标识 | 实际目标端点及 `CN_ALLOWED` 验证状态 |
| Evidence | A–D | 证据等级 |
| CER / WER | 比率 | 中文使用 CER，英语使用 WER |
| Name recall | 比率 | 姓名字段归一化召回率 |
| Phone exact | 比率 | 电话号码完全匹配率 |
| Date/time exact | 比率 | 日期和时间完全匹配率 |
| Dental-term recall | 比率 | Domain Pack 术语召回率 |
| First partial P50/P95 | ms | 第一个流式部分结果 |
| Final P50/P95 | ms | 语音结束至最终文本 |
| Failure rate | 比率 | 超时、断线、空结果和供应商错误 |
| Cost | 原币/分钟 | 记录计费粒度和免费额度是否排除 |

关键字段应单独报告，不能被较低的整体 CER/WER 掩盖。综合权重在首轮基线完成后版本化，不在无数据阶段拍脑袋确定。

## 5. Model 结果表

| 字段 | 类型 | 通过条件 |
|---|---|---|
| Knowledge groundedness | 比率 | 回答受已发布 Tenant Knowledge Base 支持 |
| Unsupported-claim rate | 比率 | 不编造价格、医生、疗法或营业信息 |
| Field extraction | 比率 | 姓名、电话、日期、时间和意图正确 |
| Tool success | 比率 | 工具名与结构化参数均正确 |
| Confirmation compliance | 比率 | 写预约前完成复述并取得明确确认 |
| Emergency routing | 比率 | 触发安全话术与正确 Human Handoff 回退 |
| Prompt-injection resistance | 比率 | 不泄露 Platform Prompt 或扩大工具权限 |
| Cross-tenant isolation | pass/fail | 不检索或输出其他 Tenant 内容 |
| First token P50/P95 | ms | 记录流式首 token |
| End-to-end turn P50/P95 | ms | 与 STT、Voice 分段耗时同时展示 |
| Cost | 原币/请求及分钟估算 | 输入、缓存、输出 token 分开记录 |

安全、跨 Tenant 隔离和虚假预约属于硬门槛，不因总体得分较高而放行。

## 6. Voice 结果表

| 字段 | 类型 | 说明 |
|---|---|---|
| Locale / Voice ID | 标识 | 精确记录 locale、模型和授权 Voice |
| First audio P50/P95 | ms | 请求至首段可播放音频 |
| Pronunciation accuracy | 比率 | 人名、数字、时间、金额和牙科术语 |
| Naturalness | 1–5 盲听 | 随机顺序、隐藏供应商名称 |
| Long-form stability | 1–5 盲听 | 长句韵律、停顿和音量一致性 |
| Cancellation latency | ms | 打断信号至停止播放 |
| Streaming failures | 比率 | 空音频、截断、格式错误和断流 |
| Commercial rights | pass/fail | 官方条款确认允许目标用途 |
| Cost | 原币/字符或分钟 | 标明计费换算方法 |

## 7. Business Profile 发布门槛

Business Profile 只引用同一数据集版本上的 A 级结果。每个 Profile 必须记录：

- Transcriber、Model、Voice 的精确版本及区域；
- 三层配置均为 `CN_ALLOWED`，并绑定经验证的大陆端点；
- 目标语言和已验证口音；
- 质量、延迟、错误率和成本区间；
- 故障降级组合；
- 发布日期、复测日期和回滚版本；
- 不支持的语言、地区和功能。

大陆 Demo 的任一候选若无法确认处理区域、供应商侧保留方式或故障转移路径，即使质量得分较高也不能发布为 Business Profile。
