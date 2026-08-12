# 可复用 AI 语音客服平台 PRD（通用 Demo 与牙科模板实例）

- 状态：Draft v0.4
- 日期：2026-07-29
- 产品定位：可复用的 AI 语音客服平台
- 第一交付物：通用平台 Demo
- 第二交付物：由通用模板生成的牙科 Demo
- 使用范围：团队内部、评委和受邀测试者
- 部署区域：中国大陆

## 1. 产品概述

本项目首先实现一个行业无关、可独立运行和验收的 AI 语音客服通用 Demo，然后通过模板配置生成牙科行业模板和示例诊所 Voice Agent。

牙科不再作为核心平台的默认业务流程。任何牙科 Prompt、术语、知识、字段和安全规则都必须存在于牙科模板或诊所实例中，不能写入 Platform Core。

平台提供以下通用能力：

- 电话或 SIP 接入；
- 实时语音识别、LLM 对话和语音输出；
- Prompt、知识库和工具调用；
- 自然打断、转人工和失败回退；
- 模板发布、实例生成和版本绑定；
- Tenant 隔离、通话日志和基础管理后台；
- Provider Adapter、模型切换和大陆区域准入。

## 2. 交付物与实施顺序

本阶段按以下顺序交付：

1. Platform Core；
2. Generic Receptionist Template；
3. 可独立运行的通用 Demo；
4. 从通用模板派生 Dental Template；
5. 从 Dental Template 创建示例诊所 Voice Agent Instance；
6. 验证牙科专用化没有修改或复制核心编排代码。

只有通用 Demo 通过验收后，牙科模板才进入验收。不能用牙科 Demo 的可运行状态代替通用平台验收。

## 3. Demo 目标

### 3.1 Platform Core

Platform Core 需要完整展示：

1. 接听入站电话；
2. 管理实时会话和通话状态；
3. 调用可替换的 Transcriber、Model 和 Voice；
4. 根据 Prompt 和知识库生成回答；
5. 执行经 Schema 校验的工具调用；
6. 支持自然打断、转人工、回拨任务和人工通知；
7. 保存基础通话记录、工具结果和阶段耗时；
8. 隔离不同 Tenant 的配置和数据；
9. 只调用通过大陆区域准入的 Provider 配置。

### 3.2 Generic Receptionist Template

通用接待员模板不包含任何牙科内容，但必须能够独立完成：

1. 回答机构名称、地址、营业时间、服务和常见问题；
2. 收集姓名、联系方式、事项、日期和时间；
3. 查询通用预约空档；
4. 完成通用预约、改期和取消；
5. 在写操作前复述信息并取得确认；
6. 找不到可靠知识时说明无法确认；
7. 工具失败时创建回拨任务并通知人工；
8. 测试者要求人工时进行转接或进入回拨流程。

### 3.3 Dental Template 与诊所实例

牙科专用化需要证明：

1. Dental Template 由已发布的 Generic Receptionist Template 派生；
2. 专用化只修改模板配置，不修改 Platform Core；
3. 牙科 Prompt、知识库结构、业务字段、术语和安全规则被正确加载；
4. 示例诊所实例拥有独立的 Prompt、知识库、Voice、工具连接和日志；
5. 牙科实例能完成咨询、预约、改期、取消和人工回退。

## 4. Demo 非目标

本阶段不实现或不验收：

- 主动外呼、诊后回访和营销电话；
- 面向真实患者的公开生产服务；
- 开场强制声明 AI 身份或开始录音；
- 多区域同步、跨境复制和海外生产部署；
- 完整计费、套餐、发票和供应商成本结算；
- 模板市场、模板交易和第三方模板发布；
- 由 LLM 动态生成或执行平台代码；
- 任意真人声音克隆；
- 大规模生产容量、跨区域容灾和完整 SLA；
- AI 医疗诊断或个性化治疗决策；
- 所有诊所管理系统和日历软件的正式连接器。

上述内容可在进入真实患者试点前重新设计，不能直接沿用内部 Demo 的简化规则。

“创建回拨任务”只表示生成一条由工作人员处理的待办和通知，不代表 Demo 会自动拨出电话。

## 5. 用户与权限

### 5.1 Platform Operator

- 管理 Transcriber、Model、Voice 和 Provider Adapter；
- 管理 Provider 区域准入；
- 创建、验证、发布和停用平台模板；
- 设置 Platform Prompt 和基础安全规则；
- 查看平台运行状态；
- 不默认查看 Tenant 的完整通话内容。

### 5.2 Tenant Administrator

- 从已发布模板创建 Voice Agent Instance；
- 填写机构配置并编辑允许覆盖的 Tenant Prompt；
- 上传、发布和更新 Tenant Knowledge Base；
- 选择业务档位和预设 Voice；
- 配置工具连接和人工通知对象；
- 查看本 Tenant 的通话、预约和回拨任务；
- 不能修改 Platform Core、Platform Prompt 或模板保护字段。

### 5.3 Tenant Staff

- 查看被授权的通话和预约结果；
- 接收人工转接或回拨通知；
- 完成回拨任务并更新状态。

## 6. 模板与实例模型

### 6.1 Platform Core

Platform Core 是行业无关的运行时和管理能力，不包含诊所、餐厅或其他行业判断。

### 6.2 Generic Receptionist Template

平台维护的通用接待员基础模板，定义通用信息收集、FAQ、预约、转人工和失败回退流程。

### 6.3 Domain Template

由已发布的通用模板派生的行业配置包。Dental Template 是本阶段第一个 Domain Template。

### 6.4 Voice Agent Instance

Tenant 从已发布模板创建的可运行实例。实例保存 Tenant 自己的 Prompt、知识库、工具凭据、Voice 和日志。

### 6.5 Template Version

- 模板发布后版本不可原地修改；
- 新修改产生新版本；
- Domain Template 发布时保存父 Template Version 和完全解析后的配置快照，不使用运行时动态继承；
- 实例固定绑定一个 Template Version；
- 模板升级必须由 Tenant Administrator 明确触发；
- 升级不能覆盖 Tenant 自己的知识库和允许覆盖字段；
- 停用模板只阻止创建新实例，不中断已绑定该版本的现有实例；
- 不同实例之间不得共享可变 Tenant 数据。

“生成专用 Demo”指复制、验证并版本化模板配置，不是让 LLM 编写或执行代码。

## 7. 模板配置结构

每个模板至少包含：

| 配置 | 作用 |
|---|---|
| Template Metadata | 名称、类型、版本、父模板和发布状态 |
| Required Fields | 创建实例时必须填写的机构字段 |
| Prompt Fragments | 角色、语气、流程和行业约束 |
| Knowledge Schema | 知识库分类、必备内容和示例结构 |
| Tool Definitions | 工具名称、JSON Schema、确认和回退规则 |
| Collection Fields | 对话中需要收集的业务字段 |
| Fallback Rules | 转人工、回拨和通知策略 |
| Voice Profile | 允许的语言、Voice 和业务档位 |
| Domain Terms | STT 热词和检索术语 |
| Evaluation Scenarios | 发布前必须通过的模板测试场景 |

模板发布前必须验证必填字段、Prompt 组合、工具 Schema、知识库引用、模型准入和回退规则。验证失败的模板不能创建实例。

## 8. 可复用运行时配置

每个 Voice Agent Instance 由以下运行时配置组成：

| 配置 | 作用 | 更换行业时是否通常修改 |
|---|---|---|
| Deployment Region | 绑定应用、数据和模型处理所在区域 | 按市场部署时修改 |
| Transcriber | 将来电语音转换为实时文字 | 可能，取决于语言和口音 |
| Model | 理解对话、检索知识、决定回复或工具调用 | 可能，取决于质量和成本 |
| Voice | 将回复文字转换为指定音色的语音 | 是 |
| Tenant Prompt | 定义机构身份、语气和业务流程 | 是 |
| Knowledge Base | 提供机构和行业事实 | 是 |
| Tool Set | 提供预约、查询、转接等动作 | 是 |
| Fallback Rules | 定义失败后的转人工、回拨和通知 | 少量修改 |

普通 Tenant 用户只选择 Business Profile 和预设 Voice，不直接组合未经验证的底层模型。

当前 Demo 的所有 Tenant 固定绑定 `cn-mainland`，界面不开放区域切换。

## 9. 核心架构

```text
中国大陆区域边界
  ├─ 电话/SIP
  ├─ Platform Core
  │    ├─ 实时编排与会话状态
  │    ├─ VAD 与自然打断
  │    ├─ Prompt / Knowledge / Tool Runtime
  │    ├─ 模板与实例加载
  │    └─ 日志与失败回退
  ├─ Provider Adapters
  │    ├─ Transcriber（大陆端点）
  │    ├─ Model（大陆端点）
  │    └─ Voice（大陆端点）
  └─ 数据库、对象存储、向量库与日志
```

Provider 可被接入不代表可以被当前区域调用。大陆实例只能使用通过大陆区域准入的配置。

## 10. 通用 Demo 流程

### 10.1 入站咨询

1. 系统使用实例配置的话术接听；
2. Transcriber 将语音转换为实时文字；
3. Model 结合 Prompt 和已发布知识库判断意图；
4. 找到可靠信息时回答；
5. 信息不足时说明无法确认，并提供转人工或回拨选项；
6. Voice 播放回复；
7. 系统保存 Call Record。

内部 Demo 不强制在开场声明 AI 身份或录音。进入真实用户试点前，需要重新确认适用的话术和录音策略。

### 10.2 信息收集与通用预约

1. Model 按模板收集姓名、联系方式、事项、日期和时间；
2. Scheduling Adapter 查询可用时间；
3. AI 复述关键字段；
4. 测试者确认后执行预约、改期或取消；
5. 工具成功时明确返回最终结果；
6. 平台记录工具、参数和结果。

Generic Receptionist Template 默认连接内置 Demo Scheduling Authority。它使用虚构空档并真实保存 Demo 预约结果，因此在没有第三方日历凭据时仍能完整演示读写流程。外部日历只能通过相同 Scheduling Adapter 接口替换，不能改变对话或确认逻辑。

### 10.3 工具失败

当工具超时、报错或结果不明确时：

1. AI 不得声称操作已经成功；
2. 不自动重复可能造成重复写入的操作；
3. 告知测试者当前未能完成；
4. 创建包含联系人、意图和已收集信息的回拨任务；
5. 通知指定 Tenant Staff；
6. Call Record 保存失败原因和回拨任务 ID。

### 10.4 转人工

- 测试者主动要求人工时发起转接；
- 无人接听时创建回拨任务并通知人工；
- 没有可用工具或模型配置时进入相同回退流程。

## 11. 牙科模板生成

### 11.1 生成流程

1. Platform Operator 选择已发布的 Generic Receptionist Template Version；
2. 创建新的 Dental Template 草稿；
3. 填写牙科必填字段、Prompt Fragments、Knowledge Schema、Tool Definitions、Domain Terms 和安全规则；
4. 运行模板验证和牙科场景测试；
5. 验证通过后发布不可变的 Dental Template Version；
6. 从该版本创建示例诊所实例；
7. 填写诊所信息并连接预约和人工通知工具；
8. 运行实例级验收。

### 11.2 牙科专用配置

Dental Template 包含：

- 牙科接待角色、用词和流程；
- 诊所名称、地址、营业时间、服务、价格说明和医生信息；
- 项目、医生、首次就诊状态等预约字段；
- 牙科术语和 Transcriber 热词；
- 标准普通话 Voice；
- 不进行诊断的限制；
- 明显紧急描述触发人工或当地急救服务提示。

### 11.3 专用化边界

生成牙科 Demo 时不得：

- 修改 Platform Core；
- 复制实时编排代码；
- 在 Provider Adapter 中加入牙科判断；
- 把某家诊所的 Prompt 或知识写入 Dental Template；
- 让一个诊所实例读取另一个实例的数据。

若牙科专用化必须修改核心公共接口，则视为通用 Demo 的复用边界未通过验收。

## 12. Prompt 与知识库

系统保留两级 Prompt：

1. Platform Prompt：由 Platform Operator 管理，Tenant 不可见；
2. Tenant Prompt：由模板提供默认内容，Tenant Administrator 只能编辑允许覆盖的品牌、语气、称呼和业务流程。

运行时合并优先级为：Platform Policy → Platform Prompt → 已发布模板的受保护 Prompt Fragments → Tenant 允许覆盖字段。Tenant 配置不能取消上层安全和权限限制。

基本原则：

- Prompt 管行为；
- Knowledge Base 管事实；
- Template 管结构、必填字段和默认流程；
- 找不到事实时不自行编造；
- Domain Terms 同时用于知识检索和 Transcriber 热词。

Demo 支持上传文件、解析内容、预览并发布知识库。

## 13. 实时对话与打断

- 测试者提出新问题时可以打断 AI；
- “嗯、好的、对”等附和词不应终止当前回答；
- 确认是真正的新意图后，停止未播放语音并回答新问题；
- 打断后保留已经确认的字段和工具状态；
- 工具正在执行时说明当前状态，避免重复提交。

## 14. 语言与 Voice

每个实例指定主要语言和预设 Voice。

当前测试重点：

- 江浙口音普通话输入；
- 标准普通话 Voice 输出；
- 使用大陆候选模型对 ENG-AU、ENG-US 和 ENG-GB 做次级扩展验证；
- 通话中的简单中英混说。

Voice 必须记录 Provider、Model、Voice ID、Locale 和版本。Demo 不开放任意声音克隆。

## 15. 大陆部署与模型准入

当前 Demo 采用单一 China Regional Cell。以下组件全部部署或托管在中国大陆：

- Platform Core 和后台管理服务；
- 模板仓库和实例配置；
- 关系数据库、对象存储、向量库、缓存和日志；
- 录音、转写、Prompt、知识库、预约和回拨任务；
- 备份、监控数据和测试结果；
- Transcriber、Model 和 Voice 的实时处理端点。

本阶段不向雅加达或其他海外区域同步数据。境外 Provider 不作为大陆 Demo 的默认、降级或关键链路。

Provider Registry 至少记录：

- `provider`、`model_id` 和 `model_version`；
- `api_endpoint` 和 `processing_region`；
- `storage_region` 和供应商侧保留方式；
- `commercial_status` 和 `region_eligibility`；
- 最近验证日期和基准测试版本。

配置只有同时满足大陆端点、区域与保留可确认、商业条件可接受、统一基准达标且不会回退境外时，才能标记为 `CN_ALLOWED`。

## 16. 基础数据与日志

Demo 保存：

- 模板 ID、父模板、版本和发布时间；
- 实例 ID、Tenant ID 和绑定模板版本；
- 通话开始和结束时间；
- 基础转写和 AI 回复文本；
- 工具调用和结果；
- 打断、转人工和错误事件；
- 预约结果或回拨任务；
- 各处理阶段的基础耗时。

Demo 只使用虚构患者和测试数据。所有数据及备份保存在中国大陆。

## 17. Demo 性能目标

- 支持至少 10 路内部并发演示；
- 用户结束说话到 AI 开始出声：P95 不超过 2 秒；
- 打断后快速停止未播放语音；
- 工具失败产生可查看的错误记录；
- 供应商凭据缺失时显示未配置，不伪造成功结果；
- 模板和实例加载不能破坏 Tenant 隔离。

50 路压力测试、生产 SLA 和多区域容灾留到下一阶段。

## 18. Demo 验收标准

### 18.1 Gate A：通用 Demo

通用 Demo 必须先满足：

1. 不加载任何牙科内容也能完成一通入站咨询；
2. 能根据通用知识库回答机构信息；
3. 能收集模板定义的字段；
4. 能完成通用预约、改期或取消；
5. 没有第三方日历凭据时，内置 Demo Scheduling Authority 仍会保存并返回可查看的测试预约；
6. 写操作前会复述并获得确认；
7. 工具失败时创建回拨任务、通知人工且不虚报成功；
8. 能自然打断，附和词不会误打断；
9. 能更换至少一组 Transcriber、Model 或 Voice 配置；
10. 能创建、验证、发布和版本化 Generic Receptionist Template；
11. 能从已发布模板创建隔离的 Voice Agent Instance；
12. 能查看基础通话、工具和回拨日志；
13. 应用、存储和模型请求均位于中国大陆；
14. 运行时不能调用未标记为 `CN_ALLOWED` 的配置；
15. P95 响应达到 2 秒目标，或明确展示未达标阶段耗时。

### 18.2 Gate B：牙科专用化

Gate A 通过后，牙科 Demo 必须满足：

1. Dental Template 的父版本是已发布的 Generic Receptionist Template；
2. 牙科专用化没有修改或复制 Platform Core；
3. 牙科 Prompt、Knowledge Schema、工具字段、Domain Terms 和安全规则均来自模板；
4. 能从 Dental Template 创建至少两个相互隔离的诊所实例；
5. 两个实例的 Prompt、知识库、工具凭据和日志不能互相读取；
6. 牙科实例能完成咨询、预约、改期、取消和人工回退；
7. AI 不进行诊断，明显紧急描述触发固定安全流程；
8. 停用 Dental Template 只阻止创建新实例，不影响通用 Demo 或已绑定该版本的牙科实例；
9. 新版本模板不会自动覆盖已有实例；
10. 牙科验收不新增核心行业判断。

## 19. 后续生产化事项

真实用户或公众使用前，需要重新增加并验证：

- AI 身份和录音告知策略；
- 数据保留、删除和访问审计；
- 真实号码、SIP 和通信合规；
- 外呼、患者授权和退订机制；
- 计费、配额和供应商成本控制；
- 模板审批、签名、迁移和回滚工具；
- 更完整的医疗安全、隐私和法律审查；
- 50 路以上压力测试、容灾和 SLA；
- 按市场新增彼此隔离的海外 Regional Cell。

这些事项不属于当前内部 Demo，但不能因为 Demo 省略而被视为生产环境已满足。
