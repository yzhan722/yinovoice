# PostgreSQL MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `platform-api` 搭好 PostgreSQL/Alembic，并用 Postgres Adapter 实现现有两个 Repository，使实例配置与通话 Transcript 重启不丢失。

**Architecture:** Docker Compose 提供本机 PostgreSQL 17；SQLAlchemy 2 async + asyncpg 访问；Alembic 管理五张核心表；`create_app` 在设置 `DATABASE_URL` 时切换到 Postgres Adapter，否则保持内存仓储。API 路由与 Pydantic 领域模型不变。

**Tech Stack:** PostgreSQL 17, SQLAlchemy 2.x asyncio, asyncpg, Alembic, FastAPI, pytest-asyncio, Docker Compose

## Global Constraints

- 工作目录：`E:\YinoVapi\.worktrees\yino-voice-stage1\YinoVoicePlatform\platform-api`（及同级 `docker-compose.yml`）
- 规格：`docs/superpowers/specs/2026-08-11-postgres-mvp-design.md`
- 保留 `CustomerServiceRepository` / `CallRecordRepository` Protocol 签名
- 不上 Redis/Kafka/Mongo/pgvector；录音文件不进库
- 未配置 `DATABASE_URL` 时现有测试与内存行为不变
- 密钥不提交；`.env.example` 仅占位
- 未获用户明确要求时不要 `git commit`

---

### Task 1: Compose + 依赖 + 设置 + Alembic 五表迁移 ✅ COMPLETED

**Files:**
- Create: `docker-compose.yml`（仓库 `YinoVoicePlatform/` 根）
- Create: `platform-api/alembic.ini`
- Create: `platform-api/migrations/env.py`
- Create: `platform-api/migrations/script.py.mako`
- Create: `platform-api/migrations/versions/20260811_0001_core_tables.py`
- Create: `platform-api/src/yino_platform_api/db/__init__.py`
- Create: `platform-api/src/yino_platform_api/db/engine.py`
- Create: `platform-api/src/yino_platform_api/db/models.py`
- Create: `platform-api/src/yino_platform_api/db/seed.py`
- Modify: `platform-api/pyproject.toml`（增加 sqlalchemy/asyncpg/alembic；dev 增加 pytest-asyncio 已有）
- Modify: `platform-api/.env.example`
- Modify: `platform-api/src/yino_platform_api/config.py`
- Test: `platform-api/tests/test_db_migrations.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `PlatformSettings.database_url: str | None`
  - `create_engine(database_url: str) -> AsyncEngine`
  - `session_factory(engine) -> async_sessionmaker[AsyncSession]`
  - SQLAlchemy models: `Tenant`, `AgentTemplateVersion`, `VoiceAgentInstance`, `CallRecordRow`, `CallMessageRow`
  - `async def ensure_demo_seed(session: AsyncSession) -> None`
  - Alembic revision `20260811_0001` 创建五表 + 可选 SQL 种子也可放在 `ensure_demo_seed`

- [ ] **Step 1: 在 `YinoVoicePlatform/docker-compose.yml` 增加 Postgres**

```yaml
services:
  postgres:
    image: postgres:17
    environment:
      POSTGRES_USER: yino
      POSTGRES_PASSWORD: yino
      POSTGRES_DB: yino_platform
    ports:
      - "5432:5432"
    volumes:
      - yino_pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U yino -d yino_platform"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  yino_pg_data:
```

- [ ] **Step 2: 更新 `pyproject.toml` 依赖**

在 `dependencies` 增加：

```toml
"sqlalchemy[asyncio]>=2.0,<3",
"asyncpg>=0.30,<1",
"alembic>=1.14,<2",
```

安装：

```bat
cd /d E:\YinoVapi\.worktrees\yino-voice-stage1\YinoVoicePlatform\platform-api
python -m pip install -e ".[dev]"
```

- [ ] **Step 3: `config.py` 增加可选 `database_url`**

```python
database_url: str | None = None
```

`.env.example` 增加：

```dotenv
# DATABASE_URL=postgresql+asyncpg://yino:yino@127.0.0.1:5432/yino_platform
```

- [ ] **Step 4: 实现 `db/models.py`（表名与规格一致）**

关键点：
- `voice_agent_instances.voice_config` / `response_config` → `JSONB`
- `platform_prompt` / `tenant_prompt` → `Text`
- `call_records` 复合 FK 到 `voice_agent_instances(tenant_id, id)`
- `call_messages` PK `(tenant_id, call_record_id, sequence)` + CASCADE

- [ ] **Step 5: Alembic `env.py` 使用 async URL 与 `Base.metadata`**

`migrations/env.py` 从环境变量 `DATABASE_URL` 读取；`target_metadata = Base.metadata`。

手写 revision `20260811_0001_core_tables.py`（不要盲目依赖 autogenerate 不审查）：创建五表、索引、CHECK、复合唯一/外键。

- [ ] **Step 6: `seed.py` 写入 Demo Tenant + Template Version + Demo Instance**

使用领域常量：

```python
from yino_platform_api.domain.customer_service import (
    DEMO_CUSTOMER_SERVICE_ID,
    DEMO_TENANT_ID,
    CustomerServiceInstance,
)
```

`ensure_demo_seed`：若不存在则插入；已存在则跳过（幂等）。

- [ ] **Step 7: 写迁移冒烟测试**

`tests/test_db_migrations.py`：若无 `DATABASE_URL` 则 `pytest.skip`；否则：

```python
@pytest.mark.asyncio
async def test_upgrade_and_seed_demo_tenant():
    # alembic upgrade head（可用 subprocess 或 command.upgrade）
    # async 查询 tenants / voice_agent_instances 存在 DEMO ids
```

- [ ] **Step 8: 本机验证**

```bat
cd /d E:\YinoVapi\.worktrees\yino-voice-stage1\YinoVoicePlatform
docker compose up -d
cd platform-api
set DATABASE_URL=postgresql+asyncpg://yino:yino@127.0.0.1:5432/yino_platform
alembic upgrade head
python -m pytest tests/test_db_migrations.py -v
```

Expected: Postgres healthy；upgrade OK；测试 PASS。

---

### Task 2: Postgres `CustomerServiceRepository` Adapter ✅ COMPLETED

**Files:**
- Create: `platform-api/src/yino_platform_api/repositories/postgres/__init__.py`
- Create: `platform-api/src/yino_platform_api/repositories/postgres/customer_services.py`
- Create: `platform-api/tests/test_postgres_customer_service_repository.py`

**Interfaces:**
- Consumes: `async_sessionmaker[AsyncSession]`, ORM `VoiceAgentInstance`, domain `CustomerServiceInstance` / `VoiceProfile` / `ResponseProfile`
- Produces: `class PostgresCustomerServiceRepository:` 实现 `get` / `save`

- [ ] **Step 1: 写失败测试（需 DATABASE_URL，否则 skip）**

覆盖：
1. `get` Demo 实例成功，字段映射含 `platform_prompt` / `tts_voice`
2. `save` 将 `version` 从 N 增到 N+1 且 CAS 成功
3. 用过期 `version`（WHERE 不匹配）`save` 抛出明确异常（如 `CustomerServiceVersionConflict`），供路由映射 409——若暂不改路由，Adapter 可在 0 行时 raise，并在 Task 4 接到路由；**本轮最小改动**：在 `routes/customer_services.py` 的 `save` 外包一层捕获该异常 → 409
4. 错误 `tenant_id` → `get` 返回 `None`

- [ ] **Step 2: 实现映射与 CAS `save`**

```python
class CustomerServiceVersionConflict(Exception):
    pass

class PostgresCustomerServiceRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None: ...

    async def get(self, instance_id: UUID, tenant_id: UUID) -> CustomerServiceInstance | None:
        # SELECT by tenant_id + id → map jsonb to VoiceProfile/ResponseProfile

    async def save(self, instance: CustomerServiceInstance) -> CustomerServiceInstance:
        # UPDATE ... WHERE tenant_id AND id AND version = instance.version - 1
        # 若行不存在：INSERT（仅种子/首次）或 raise VersionConflict
        # 推荐：存在则 CAS update；不存在则 insert version==instance.version
```

`voice_config` = `instance.voice.model_dump(mode="json")`；读回时 `VoiceProfile.model_validate(...)`。

- [ ] **Step 3: 跑测试**

```bat
set DATABASE_URL=postgresql+asyncpg://yino:yino@127.0.0.1:5432/yino_platform
python -m pytest tests/test_postgres_customer_service_repository.py -v
```

Expected: PASS

- [ ] **Step 4: 路由捕获版本冲突（最小改动）**

`routes/customer_services.py`：`save` 捕获 `CustomerServiceVersionConflict` → HTTP 409。

---

### Task 3: Postgres `CallRecordRepository` Adapter ✅ COMPLETED

**Files:**
- Create: `platform-api/src/yino_platform_api/repositories/postgres/call_records.py`
- Create: `platform-api/tests/test_postgres_call_record_repository.py`

**Interfaces:**
- Consumes: `async_sessionmaker[AsyncSession]`, ORM call tables, domain `CallRecord` / `TranscriptMessage`
- Produces: `class PostgresCallRecordRepository:` 实现 `save` / `list_for_tenant` / `get`

- [ ] **Step 1: 写失败测试**

覆盖：
1. `save` 含 2 条 messages → `get` 顺序与 sequence 一致
2. 再次 `save` 同一 id、更少 messages → 旧 message 被替换（非追加重复）
3. `list_for_tenant` 按 `created_at DESC, id DESC`，`total` 正确
4. 错误 Tenant → `get` 为 `None`
5. 指向不存在实例的 FK → 插入失败（数据库完整性）

- [ ] **Step 2: 实现事务内 save**

同一 `AsyncSession` 事务：
1. upsert `call_records` 行（按 `tenant_id, id`）
2. `DELETE FROM call_messages WHERE tenant_id=:t AND call_record_id=:id`
3. `INSERT` 当前 `record.messages`
4. commit；返回深拷贝语义的领域对象

`list_for_tenant`：count + keyset 可用 offset/limit 与现 API 一致；加载 messages（可用 selectinload 或二次查询按 record ids）。

- [ ] **Step 3: 跑测试**

```bat
python -m pytest tests/test_postgres_call_record_repository.py -v
```

Expected: PASS

---

### Task 4: `create_app` 接线 + 无库回归 ✅ COMPLETED

**Files:**
- Modify: `platform-api/src/yino_platform_api/app.py`
- Modify: `platform-api/src/yino_platform_api/db/engine.py`（如需 lifespan dispose）
- Test: `platform-api/tests/test_app_repository_wiring.py`（可选）
- 跑全量：`python -m pytest -q`

**Interfaces:**
- Consumes: Task 1–3
- Produces: `create_app()` 在 `settings.database_url` 有值时使用 Postgres repos + `ensure_demo_seed`

- [ ] **Step 1: 接线逻辑**

```python
settings = PlatformSettings()
if repository is None:
    if settings.database_url:
        engine = create_async_engine(settings.database_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        # lifespan: ensure_demo_seed; shutdown dispose
        repository = PostgresCustomerServiceRepository(sessions)
    else:
        repository = InMemoryCustomerServiceRepository([...demo...])
# call_record_repository 同样分支
```

使用 FastAPI `lifespan`：启动 `ensure_demo_seed`；关闭 `await engine.dispose()`。

- [ ] **Step 2: 无 DATABASE_URL 跑全量测试**

```bat
set DATABASE_URL=
python -m pytest -q
```

Expected: 既有测试全绿（仍走内存）。

- [ ] **Step 3: 有 DATABASE_URL 手工冒烟（CMD）**

```bat
cd /d E:\YinoVapi\.worktrees\yino-voice-stage1\YinoVoicePlatform
docker compose up -d
cd platform-api
set DATABASE_URL=postgresql+asyncpg://yino:yino@127.0.0.1:5432/yino_platform
alembic upgrade head
python -m uvicorn yino_platform_api.app:app --host 127.0.0.1 --port 8000
```

另开窗口：GET/PUT customer-service、POST call-record，重启 uvicorn 后再 GET，数据仍在。

---

### Task 5: 规格自检与文档指针 ✅ COMPLETED

**Files:**
- Modify（如需）：`platform-api/README.md` 增加「本地 Postgres」三行 CMD（无密钥）

- [ ] **Step 1: 对照规格 §6 验收清单逐项勾选**
- [ ] **Step 2: 确认第二轮表未误建**
- [ ] **Step 3: 若用户要求再提交 git**

---

## Spec coverage

| 规格项 | Task |
|---|---|
| Compose PG 16/17 | Task 1 |
| SQLAlchemy async + asyncpg + Alembic | Task 1 |
| 五张核心表 | Task 1 |
| jsonb voice/response；Prompt 正规列 | Task 1–2 |
| Transcript 消息表 | Task 1, 3 |
| 保留 Protocol；Postgres Adapter | Task 2–3 |
| 文件/录音不进库 | 无 BLOB 列（全程） |
| `create_app` 切换 | Task 4 |
| 不上 Redis/向量/第二轮表 | 未列入任务 |

## Placeholder scan

无 TBD；提交步骤服从用户「未要求不 commit」约束。
