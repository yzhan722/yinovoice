# YinoVapi Demo 数据库选型与搭建设计

> 日期：2026-08-11  
> 范围：当前中国大陆单 Regional Cell 的内部 Demo；不修改现有产品代码。  
> 依据：仓库 `CONTEXT.md`、PRD、ADR、`platform-api` 领域模型与仓储接口，以及文末官方资料。

## 1. 结论

当前 Demo 应采用 **一个 PostgreSQL 主库** 作为事务数据源，并继续沿用现有 Repository 接口逐步替换进程内仓储。建议：

- 本地开发使用 PostgreSQL 17；部署时选择中国大陆地域、受支持的 PostgreSQL 16/17 托管实例，具体小版本由云厂商当期支持矩阵决定。
- Python 数据访问层使用 SQLAlchemy 2.x async + `asyncpg`，迁移使用 Alembic；Pydantic 继续承担 API/领域输入校验，不作为数据库映射层。
- 多租户采用“共享 schema + 每张租户业务表显式 `tenant_id` + 复合外键 + PostgreSQL RLS”三层防护。RLS 是纵深防御，认证后的服务端身份才是 Tenant 来源；不能把当前可自行填写的 `X-Tenant-ID` 当作生产安全边界。
- 稳定、常查、参与约束的字段关系化；模板配置、Voice/Response Profile、工具参数等演进较快的原子配置使用 `jsonb`。PostgreSQL 官方建议大多数应用优先 `jsonb`，但也提醒大 JSON 的整行更新会取得整行锁，因此 transcript 不应做成一个不断追加的大 JSON 数组。[PostgreSQL JSON 类型](https://www.postgresql.org/docs/current/datatype-json.html)
- 录音和知识原文件放中国大陆对象存储，PostgreSQL 只保存对象键、哈希、大小、MIME、状态与保留期限；数据库、对象存储、备份、日志不得跨出 China Regional Cell。
- 知识库初期仍落 PostgreSQL。数量很小时先使用精确检索/全文检索；确有语义召回需求且固定 embedding 模型后，再给 `knowledge_chunks` 启用 pgvector。Demo 阶段不需要独立向量数据库。

不建议当前选择 SQLite（并发、RLS、部署一致性不足）、MongoDB（核心关系、版本绑定、复合完整性约束更别扭）或同时引入 PostgreSQL + 专用向量库（运维成本超出 Demo 需要）。

## 2. 从当前代码得到的约束

当前 `platform-api` 已有清晰的替换缝：`CustomerServiceRepository` 与 `CallRecordRepository` 是 Protocol，实际实现仍为 `InMemory*Repository`。数据库接入应增加 PostgreSQL 实现，而不是改写路由领域语义。

已有 API/模型要求必须保持：

- `CustomerServiceInstance` 以 UUID 标识，属于一个 Tenant，并使用整数 `version` 做乐观并发控制；更新版本不匹配返回 409。
- `CallRecord` 属于 Tenant 和 Voice Agent Instance，包含 UTC 起止时间、状态、方向、录音状态；消息有严格递增 `sequence`。
- 跨 Tenant 读取返回 404；数据库查询必须始终带 Tenant 条件。
- Agent Template 发布版本不可变，Voice Agent Instance 固定绑定一个 Template Version，升级是显式操作。
- 外部诊所系统仍是 Scheduling Authority；平台只存连接、同步状态、幂等键与审计，不复制一套“权威预约”。

## 3. 推荐数据模型

### 3.1 第一阶段必须落库

| 表 | 关键字段 | 设计要点 |
|---|---|---|
| `tenants` | `id`, `name`, `home_region`, `status`, timestamps | 当前 `home_region` 固定 `cn-mainland`，但字段保留 |
| `voice_agent_instances` | `id`, `tenant_id`, `version`, `display_name`, `organization_name`, `business_profile`, `primary_language`, `greeting`, `tenant_prompt`, `voice_config jsonb`, `response_config jsonb`, timestamps | `UNIQUE (tenant_id, id)`；更新使用 `WHERE version = :expected_version` 原子 compare-and-swap |
| `call_records` | `id`, `tenant_id`, `voice_agent_instance_id`, room/status/direction/timing, recording metadata, `created_at` | 主列表索引 `(tenant_id, created_at DESC, id DESC)` |
| `call_messages` | `tenant_id`, `call_record_id`, `sequence`, `role`, `text`, `created_at` | `PRIMARY KEY (tenant_id, call_record_id, sequence)`；避免整段 transcript JSON 的写放大与锁竞争 |

关键约束示例：

```sql
CREATE TABLE voice_agent_instances (
  id uuid NOT NULL,
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  version integer NOT NULL CHECK (version >= 1),
  display_name varchar(80) NOT NULL,
  organization_name varchar(120) NOT NULL,
  business_profile text NOT NULL,
  primary_language text NOT NULL,
  greeting varchar(300) NOT NULL,
  tenant_prompt text NOT NULL DEFAULT '',
  voice_config jsonb NOT NULL,
  response_config jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (id),
  UNIQUE (tenant_id, id)
);

CREATE TABLE call_records (
  id uuid NOT NULL,
  tenant_id uuid NOT NULL,
  voice_agent_instance_id uuid NOT NULL,
  room_name varchar(128) NOT NULL,
  status text NOT NULL CHECK (status IN ('completed','interrupted','failed')),
  direction text NOT NULL CHECK (direction IN ('web','inbound','outbound')),
  started_at timestamptz NOT NULL,
  ended_at timestamptz NOT NULL,
  duration_sec integer NOT NULL CHECK (duration_sec BETWEEN 0 AND 86400),
  recording_status text NOT NULL DEFAULT 'none'
    CHECK (recording_status IN ('none','uploading','ready','failed')),
  recording_object_key text,
  recording_mime_type text,
  recording_size_bytes bigint CHECK (recording_size_bytes >= 0),
  recording_sha256 char(64),
  recording_failure_code text,
  recording_delete_after timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (id),
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, voice_agent_instance_id)
    REFERENCES voice_agent_instances (tenant_id, id),
  CHECK (ended_at >= started_at)
);

CREATE INDEX call_records_tenant_created_idx
  ON call_records (tenant_id, created_at DESC, id DESC);
```

复合外键让数据库自身拒绝把 Tenant A 的通话挂到 Tenant B 的实例上；不能只依赖应用代码。PostgreSQL 的主键、唯一、外键和检查约束由数据库声明并执行，适合承载这类不变量。[PostgreSQL 约束](https://www.postgresql.org/docs/current/ddl-constraints.html)

乐观更新必须是一条 SQL，而不是先读后写：

```sql
UPDATE voice_agent_instances
SET display_name = :display_name,
    voice_config = :voice_config,
    response_config = :response_config,
    version = version + 1,
    updated_at = now()
WHERE tenant_id = :tenant_id
  AND id = :id
  AND version = :expected_version
RETURNING *;
```

返回 0 行时再区分 404 与 409，保持当前 API 合同。

### 3.2 第二阶段：模板、知识和审计

- `agent_templates(id, kind, name, status, created_at)`：平台级模板元数据。
- `agent_template_versions(id, template_id, version, parent_version_id, schema_version, package jsonb, published_at)`：发布后只读；`UNIQUE(template_id, version)`。
- `voice_agent_instances.template_version_id`：绑定不可变版本；不要把模板 package 复制成多份可变数据。
- `knowledge_bases(id, tenant_id, instance_id, active_version_id, ...)`。
- `knowledge_versions(id, tenant_id, knowledge_base_id, version, status, published_at, ...)`：草稿、发布版本分离。
- `knowledge_documents(id, tenant_id, knowledge_version_id, object_key, sha256, mime_type, parse_status, ...)`。
- `knowledge_chunks(id, tenant_id, document_id, ordinal, content, metadata jsonb, embedding_model_id, embedding)`。
- `tool_executions(id, tenant_id, call_record_id, tool_name, request_redacted jsonb, response_redacted jsonb, status, idempotency_key, timestamps)`。
- `callback_tasks(...)`：仅表示人工待办，不代表自动外呼。
- `audit_events(id bigint identity, tenant_id nullable, actor_id, action, resource_type, resource_id, payload_redacted jsonb, created_at)`：追加写，禁止普通应用角色更新/删除。

模板 package、工具定义、评估场景适合 `jsonb`，但 `tenant_id`、状态、版本、时间、外键、幂等键必须是类型化列。只为实际查询模式建立 JSONB GIN/表达式索引；官方文档指出定向表达式索引通常比整列通用 GIN 更小、更快。[PostgreSQL JSONB 索引](https://www.postgresql.org/docs/current/datatype-json.html#JSON-INDEXING)

### 3.3 多租户 RLS

每个请求在认证完成后开启事务，并执行参数化的：

```sql
SELECT set_config('app.tenant_id', :tenant_id, true);
```

租户表启用并强制 RLS：

```sql
ALTER TABLE call_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_records FORCE ROW LEVEL SECURITY;

CREATE POLICY call_records_tenant_isolation ON call_records
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

同样策略应用于实例、消息、知识与任务表。运行时数据库角色不得是表 owner、superuser，也不得拥有 `BYPASSRLS`；PostgreSQL 官方明确说明这些身份通常可以绕过 RLS，而 `FORCE ROW LEVEL SECURITY` 可让 owner 也受策略约束。[PostgreSQL RLS](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

`SET LOCAL`/`set_config(..., true)` 必须与业务 SQL 位于同一事务，避免连接池复用导致 Tenant 上下文泄漏。还需保留所有 repository 查询的显式 `tenant_id` 条件，使代码审查、索引使用和测试更清晰。

## 4. 知识检索与向量选型

先做以下顺序：

1. 文档和 chunk 关系化落库，按 `(tenant_id, knowledge_version_id)` 过滤。
2. 小数据集用精确搜索；需要关键词时使用 PostgreSQL 全文搜索，并保留中文分词效果的实测门槛。
3. 只有在冻结 embedding 模型、维度、距离函数并有召回评测后，才安装 pgvector、增加固定维度列。
4. 数据量小时先做 exact nearest-neighbor；数据和延迟证明有必要后再建 HNSW。HNSW 过滤发生在近邻索引扫描之后，必须先有 Tenant/知识版本过滤索引并实测召回。

pgvector 官方说明 HNSW 相比 IVFFlat 通常有更好的速度/召回权衡，但构建更慢、占用更多内存；同时建议为过滤字段建立索引，并用 `EXPLAIN (ANALYZE, BUFFERS)` 检查计划。因此 Demo 不应一开始就盲建向量近似索引。[pgvector 官方 README](https://github.com/pgvector/pgvector)

建议形态：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE knowledge_chunks ADD COLUMN embedding vector(<固定维度>);
CREATE INDEX knowledge_chunks_scope_idx
  ON knowledge_chunks (tenant_id, knowledge_version_id);
-- 召回/延迟基准证明需要后再加：
CREATE INDEX knowledge_chunks_embedding_hnsw_idx
  ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
```

不能让同一次检索跨 Tenant 或跨未发布知识版本召回；应用过滤、复合索引与 RLS 三者都要覆盖 `knowledge_chunks`。

## 5. 容量、索引与生命周期

- 当前列表查询已有 `limit/offset`；数据增长后改为 `(created_at, id)` keyset cursor，现有复合索引可直接支持。
- `call_messages` 建 `(tenant_id, call_record_id, sequence)` 主键；统计查询按真实页面再补索引，不预建大量低价值索引。PostgreSQL 多列 B-tree 在约束最左列时最有效，因此所有租户列表索引应以 `tenant_id` 开头。[PostgreSQL 多列索引](https://www.postgresql.org/docs/current/indexes-multicolumn.html)
- Demo 初期不要分区。只有通话/审计量增长、且按月删除或归档成为明确需求后，再按 `created_at` 做月度 RANGE 分区；PostgreSQL 原生支持声明式分区，但它增加迁移与唯一约束设计复杂度。[PostgreSQL 分区](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- transcript、录音、工具参数和审计分别配置保留期限；删除任务先删对象存储对象，再将元数据标记/清除，并记录审计。备份保留必须与数据删除策略一起定义。
- 时间统一 `timestamptz` + UTC；金额（未来计费）使用整数最小单位或 `numeric`，不使用浮点数。

## 6. 搭建方案

### 6.1 依赖与目录建议

在后续实现任务中增加（本调研不修改产品依赖）：

```text
platform-api/
  alembic.ini
  migrations/
    env.py
    versions/
  src/yino_platform_api/db/
    engine.py
    models.py
    tenant_context.py
  src/yino_platform_api/repositories/postgres/
```

依赖建议锁在各自主版本范围：`sqlalchemy[asyncio]`、`asyncpg`、`alembic`。SQLAlchemy 官方提供 `create_async_engine`、`async_sessionmaker` 与事务式 `AsyncSession`；同一个 `AsyncSession` 不应被多个并发 task 共享。[SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

Alembic autogenerate 只生成“候选迁移”，官方要求人工审查和修正；CI 至少执行 upgrade 到 head、schema 检查、再 downgrade/upgrade 的迁移验证。[Alembic autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)

### 6.2 本地与部署环境

- 本地：用容器启动与目标大版本一致的 PostgreSQL；需要向量时选择包含 pgvector 的官方项目镜像或自行固定扩展版本。数据库文件使用命名 volume，不提交仓库。
- 配置：`DATABASE_URL` 只在服务端 `.env.local`/Secret Manager，示例值不得含真实密码；测试数据库独立。
- 连接：每个 API 请求一个短事务；连接池从小值开始，设置 acquire/statement timeout，健康检查使用连接探测而非只返回进程存活。
- 部署：数据库、只读副本（若需要）、对象存储、备份和监控均选中国大陆地域；开启静态/传输加密、自动备份、时间点恢复与私网访问。实际 RPO/RTO、保留期需产品负责人确认后写成验收项。
- 角色：`migration_owner` 执行迁移；`app_runtime` 仅有业务 DML 且不能绕过 RLS；`ops_readonly` 只读且默认不读取完整 Tenant 内容。

### 6.3 推荐实施顺序

1. 建数据库连接、Alembic 与 `tenants`/`voice_agent_instances`/`call_records`/`call_messages` 首版迁移。
2. 编写 PostgreSQL Repository，保留现有 Protocol 与 Pydantic 响应；先做双实现测试，不双写生产数据。
3. 用事务原子实现实例版本更新；加入重启后持久化、并发 409、复合外键与跨 Tenant 拒绝测试。
4. 加入 RLS 和不同数据库角色的集成测试，包括“漏写 Tenant WHERE 仍无法越权”的负向测试。
5. 将录音从本地目录迁到大陆对象存储，数据库只留 metadata；验证上传失败补偿和删除流程。
6. 再实现 Template Version、Knowledge Version、工具执行与审计；最后用评测决定是否启用 pgvector。

## 7. 验收清单

- API 重启后实例配置和通话记录不丢失。
- 两个 Tenant 使用相同资源 UUID 组合测试时仍不能交叉读写；跨 Tenant 外键插入失败。
- 两个并发更新使用相同 `expected_version` 时仅一个成功，另一个稳定返回 409。
- transcript `sequence` 重复或倒序写入被唯一/业务约束拒绝。
- 数据库备份、对象存储和日志均位于大陆地域；恢复演练能达到已批准的 RPO/RTO。
- 录音对象键不可由客户端任意指定，下载必须经过 Tenant 授权；数据库中不存在音频 BLOB。
- 模板发布版本不可更新；实例升级必须显式记录来源和审计事件。
- 若启用向量检索，召回评测覆盖 Tenant/版本过滤，且不存在跨 Tenant chunk。

## 8. 仍需产品/运维确认的决策

- Demo 数据各类别（transcript、录音、审计、知识源文件）的具体保留天数。
- 托管 PostgreSQL 和对象存储的大陆云厂商、可用区、RPO/RTO、预算。
- 当前 Demo 是否只保留固定 Tenant，还是立即接入真实认证与成员/RBAC 表；在真实认证完成前，`X-Tenant-ID` 只能作为 Demo 路由参数。
- embedding 供应商、模型、维度和更新策略；没有离线评测结果前不承诺向量索引方案。

## 9. 官方资料

- [PostgreSQL：JSON Types](https://www.postgresql.org/docs/current/datatype-json.html)
- [PostgreSQL：Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)
- [PostgreSQL：Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [PostgreSQL：Multicolumn Indexes](https://www.postgresql.org/docs/current/indexes-multicolumn.html)
- [PostgreSQL：Table Partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [SQLAlchemy 2.0：Asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic：Auto Generating Migrations](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- [pgvector 官方仓库与 README](https://github.com/pgvector/pgvector)
