# 通用 Demo 与牙科模板设计

## 背景

上一版 PRD 虽然把产品定义为可复用平台，但主要流程和验收仍直接围绕牙科展开。团队决定改变实施顺序：先完成并验收行业无关的通用 Demo，再利用已发布模板生成牙科模板和诊所实例。

## 已选择方案

采用三层模板架构：

```text
Platform Core
  → Generic Receptionist Template
  → Dental Template
  → Clinic Voice Agent Instance
```

没有选择在核心代码中使用行业开关，因为这会让牙科判断逐渐进入编排层；也没有建设模板市场，因为模板交易、第三方发布和复杂审批不属于当前 Demo。

## Platform Core

Platform Core 负责电话接入、实时编排、Transcriber、Model、Voice、Prompt、知识库、工具、打断、转人工、回拨、日志、Tenant 隔离、模板加载和大陆模型准入。

Platform Core 不包含牙科术语、诊所字段、医疗安全话术或牙科工具判断。行业专用化需要修改核心代码时，通用边界即判定失败。

## Generic Receptionist Template

通用接待员模板必须在没有任何牙科内容时独立运行。它提供机构 FAQ、姓名与联系方式收集、事项和时间收集、通用预约/改期/取消、确认、知识不足回退、转人工和回拨任务。

模板至少包含元数据、必填字段、Prompt Fragments、Knowledge Schema、Tool Definitions、Collection Fields、Fallback Rules、Voice Profile、Domain Terms 和 Evaluation Scenarios。

通用模板默认使用内置 Demo Scheduling Authority。该工具以虚构空档完成真实的 Demo 读写和结果查询，使通用验收不依赖第三方日历凭据；以后可以通过同一个 Scheduling Adapter 接口替换为外部日历。

## Dental Template 与实例

Dental Template 从一个已发布的 Generic Receptionist Template Version 派生。它增加牙科角色和话术、诊所知识结构、项目与医生等字段、牙科术语、STT 热词、不诊断限制和紧急情况流程。

诊所从已发布的 Dental Template 创建 Voice Agent Instance，再填写诊所名称、地址、营业时间、医生、服务、日历连接、通知人员、Voice 和知识库。模板不能包含某一家诊所的可变数据。

“生成”是复制、验证和版本化配置，不是让 LLM 生成平台代码。

## 版本与隔离

- 已发布 Template Version 不可原地修改；
- Domain Template 发布时保存父版本和完全解析后的配置快照，不做运行时动态继承；
- 实例固定绑定一个版本；
- 升级必须显式触发；
- 升级不能覆盖 Tenant 自有知识和允许覆盖字段；
- 两个诊所实例的 Prompt、知识、凭据、通话和日志完全隔离；
- 停用 Dental Template 只阻止新建实例，不影响通用 Demo 或已存在实例。

## 错误处理

- 缺少必填字段、工具 Schema、回退规则或评估场景时阻止模板发布；
- 工具失败时不虚报成功，创建回拨任务并通知人工；
- 没有可用 `CN_ALLOWED` 模型时进入人工或回拨流程；
- 模板版本不兼容时拒绝升级并保留原实例版本；
- 专用化要求修改核心行业逻辑时停止发布并修正模板接口。

## 验收顺序

Gate A 独立验收通用 Demo，包括完整通话、通用知识、信息收集、通用预约、打断、失败回退、模板发布、实例生成、Tenant 隔离和大陆模型准入。

Gate B 在 Gate A 通过后验收牙科专用化，包括模板继承、牙科配置加载、至少两个诊所实例隔离、牙科流程和安全规则，以及“零核心行业修改”。

## 部署约束

Platform Core、模板仓库、实例配置、Tenant 数据和模型处理继续位于 China Regional Cell。模板化不改变 `CN_ALLOWED` 准入规则，也不能通过模板配置绕过大陆区域边界。
