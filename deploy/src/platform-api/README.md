# Yino Platform API

Platform API 是本地 AI 语音客服纵向切片的服务端控制面。它提供种子 Demo 客服配置、
带乐观版本检查的更新、LiveKit 房间连接令牌，以及网页语音 Demo 通话记录。

> **Demo-only 持久化**：客服配置和通话记录仓库都只存在于当前 API 进程内存中。
> 服务重启后，网页语音通话记录会全部丢失，客服配置恢复为种子数据。本模块不是电话
> CDR，也不包含数据库、生产认证或全局运营端 RBAC。

## 本地配置

从示例创建未跟踪的本地文件：

~~~powershell
Copy-Item .env.example .env.local
~~~

本地自托管 LiveKit 使用：

~~~dotenv
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_URL=http://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
LIVEKIT_AGENT_NAME=yino-customer-service
~~~

devkey / secret 只适用于 LiveKit --dev 的本机开发模式，生产环境必须替换。
API key 和 secret 只保留在服务端 .env.local，不进入响应、前端环境或日志。
LIVEKIT_URL 是可公开的连接地址。供应商密钥不属于 Platform API，必须只保留在
voice-agent/.env.local。

## 启动

先启动本地 LiveKit Server，再在本目录运行：

~~~powershell
.\.venv\Scripts\python.exe -m uvicorn yino_platform_api.app:app --reload --port 8000
~~~

服务地址为 http://localhost:8000，健康检查为 GET /health。Web 控制台使用固定
Demo Tenant 请求头访问：

- GET /api/v1/customer-services/{id}：读取租户内配置；
- PUT /api/v1/customer-services/{id}：按 expected_version 更新配置；
- POST /api/v1/customer-services/{id}/livekit-token：签发短期、房间范围令牌并调度
  yino-customer-service worker；
- POST /api/v1/call-records：保存 completed / interrupted / failed 网页 Demo 记录；
- GET /api/v1/call-records?limit=&offset=：按 Tenant 新到旧分页；
- GET /api/v1/call-records/{id}：读取同一 Tenant 内详情与 final transcript。

跨 Tenant 的配置和令牌请求均返回 404。令牌响应只包含公开 LiveKit URL、房间名、
参与者标识和短期令牌；不包含 API secret、内部调度元数据、participant attributes
或 room config。Platform API 使用 LIVEKIT_API_URL 的鉴权服务端 API 创建 named-agent
dispatch，且只在调度创建成功后签发浏览器令牌。

通话记录同样要求 X-Tenant-ID，创建前校验客服实例归属；跨 Tenant 详情返回 404。
记录方向固定为 web，不虚构电话号码，只接收 final transcript。

## 验证

测试不会连接 LiveKit 或供应商：

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m ruff check --no-cache src tests
~~~

这些检查覆盖 Tenant 拒绝、版本冲突、房间范围令牌、短期有效期、无 secret 响应，
以及 Demo 记录的严格校验、租户隔离、分页和 CORS。真实浏览器与语音链路仍需按
平台根 README 的十一项清单手工验收。
