from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from .config import PlatformSettings
from .db.engine import create_db_engine, create_session_factory
from .db.seed import ensure_demo_seed
from .domain.customer_service import (
    DEMO_CUSTOMER_SERVICE_ID,
    DEMO_TENANT_ID,
    CustomerServiceInstance,
)
from .repositories.call_records import (
    CallRecordRepository,
    InMemoryCallRecordRepository,
)
from .repositories.customer_services import (
    CustomerServiceRepository,
    InMemoryCustomerServiceRepository,
)
from .repositories.postgres import (
    PostgresCallRecordRepository,
    PostgresCustomerServiceRepository,
)
from .routes.call_records import create_router as create_call_record_router
from .routes.customer_services import create_router as create_customer_service_router
from .services.livekit_tokens import (
    AgentDispatcher,
    LiveKitAgentDispatcher,
    LiveKitTokenIssuer,
)


def create_app(
    repository: CustomerServiceRepository | None = None,
    *,
    agent_dispatcher: AgentDispatcher | None = None,
    call_record_repository: CallRecordRepository | None = None,
    recording_dir: Path | str | None = None,
    call_recording_max_bytes: int | None = None,
) -> FastAPI:
    settings = PlatformSettings()
    engine: AsyncEngine | None = None
    sessions: async_sessionmaker[AsyncSession] | None = None

    if settings.database_url and (
        repository is None or call_record_repository is None
    ):
        engine = create_db_engine(settings.database_url)
        sessions = create_session_factory(engine)

    if repository is None:
        if sessions is not None:
            repository = PostgresCustomerServiceRepository(sessions)
        else:
            repository = InMemoryCustomerServiceRepository(
                [
                    CustomerServiceInstance.demo(
                        instance_id=DEMO_CUSTOMER_SERVICE_ID,
                        tenant_id=DEMO_TENANT_ID,
                    )
                ]
            )
    if call_record_repository is None:
        if sessions is not None:
            call_record_repository = PostgresCallRecordRepository(sessions)
        else:
            call_record_repository = InMemoryCallRecordRepository()

    if agent_dispatcher is None:
        agent_dispatcher = LiveKitAgentDispatcher(
            api_url=settings.livekit_api_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        )
    token_issuer = LiveKitTokenIssuer(
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
        server_url=settings.livekit_url,
        agent_name=settings.livekit_agent_name,
        dispatcher=agent_dispatcher,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if engine is not None and sessions is not None:
            async with sessions() as session:
                await ensure_demo_seed(session)
        yield
        if engine is not None:
            await engine.dispose()

    app = FastAPI(
        title="Yino Platform API",
        version="0.1.0",
        lifespan=lifespan,
    )
    # Local demo console may open as localhost or 127.0.0.1; Vite may fall
    # back to adjacent ports when 3003 is already taken.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3003",
            "http://localhost:3004",
            "http://localhost:5173",
            "http://127.0.0.1:3003",
            "http://127.0.0.1:3004",
            "http://127.0.0.1:5173",
        ],
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
        allow_credentials=False,
        allow_methods=["GET", "PUT", "POST"],
        allow_headers=["Content-Type", "X-Tenant-ID"],
    )
    resolved_recording_dir = (
        Path(recording_dir)
        if recording_dir is not None
        else Path(settings.call_recording_dir)
    )
    resolved_max_bytes = (
        call_recording_max_bytes
        if call_recording_max_bytes is not None
        else settings.call_recording_max_bytes
    )

    app.include_router(create_customer_service_router(repository, token_issuer))
    app.include_router(
        create_call_record_router(
            call_record_repository,
            repository,
            recording_dir=resolved_recording_dir,
            recording_max_bytes=resolved_max_bytes,
        )
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.state.persistence = (
        "postgres" if sessions is not None else "memory"
    )
    return app


app = create_app()
