# 关键规则由代码策略执行而不是只依赖 Prompt

医疗安全、外呼授权、工具权限、数据访问和必要披露由 Platform Policy 在代码层强制执行，Platform Prompt 负责引导模型，Tenant Prompt 只控制品牌与业务行为。该分层牺牲一部分租户自由度，以换取可审计、不可被低优先级 Prompt 扩权且更能抵抗提示注入的安全边界。
