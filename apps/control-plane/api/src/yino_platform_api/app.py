from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

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
from .repositories.appointments import (
    AppointmentRepository,
    InMemoryAppointmentRepository,
)
from .repositories.call_records import (
    CallRecordRepository,
    InMemoryCallRecordRepository,
)
from .repositories.callback_tasks import (
    CallbackTaskRepository,
    InMemoryCallbackTaskRepository,
)
from .repositories.customer_services import (
    CustomerServiceRepository,
    InMemoryCustomerServiceRepository,
)
from .repositories.phone_numbers import (
    InMemoryPhoneNumberRepository,
    PhoneNumberRepository,
)
from .repositories.postgres import (
    PostgresAppointmentRepository,
    PostgresCallbackTaskRepository,
    PostgresCallRecordRepository,
    PostgresCustomerServiceRepository,
    PostgresNotificationRepository,
    PostgresPhoneNumberRepository,
    PostgresSchedulingRepository,
    PostgresToolInvocationRepository,
)
from .repositories.scheduling import (
    InMemorySchedulingRepository,
    SchedulingRepository,
)
from .repositories.tool_invocations import (
    InMemoryToolInvocationRepository,
    ToolInvocationRepository,
)
from .routes.appointments import create_router as create_appointment_router
from .routes.call_records import create_router as create_call_record_router
from .routes.call_sessions import create_router as create_call_session_router
from .routes.callback_tasks import create_router as create_callback_task_router
from .routes.customer_services import create_router as create_customer_service_router
from .routes.dashboard import create_router as create_dashboard_router
from .routes.notifications import create_router as create_notification_router
from .routes.phone_numbers import create_router as create_phone_number_router
from .routes.scheduling import create_router as create_scheduling_router
from .routes.tool_invocations import create_router as create_tool_invocation_router
from .services.call_lifecycle import CallLifecycleService
from .services.livekit_egress import RecordingEgressService, sink_from_settings
from .services.livekit_tokens import (
    AgentDispatcher,
    LiveKitAgentDispatcher,
    LiveKitTokenIssuer,
)
from .services.notifications import (
    InMemoryNotificationRepository,
    NotificationRepository,
    NotificationService,
    SmtpNotificationSink,
)
from .services.tool_execution import ToolExecutionService


def create_app(
    repository: CustomerServiceRepository | None = None,
    *,
    agent_dispatcher: AgentDispatcher | None = None,
    call_record_repository: CallRecordRepository | None = None,
    appointment_repository: AppointmentRepository | None = None,
    callback_task_repository: CallbackTaskRepository | None = None,
    phone_number_repository: PhoneNumberRepository | None = None,
    scheduling_repository: SchedulingRepository | None = None,
    tool_invocation_repository: ToolInvocationRepository | None = None,
    notification_repository: NotificationRepository | None = None,
    recording_dir: Path | str | None = None,
    call_recording_max_bytes: int | None = None,
) -> FastAPI:
    settings = PlatformSettings()
    engine: AsyncEngine | None = None
    sessions: async_sessionmaker[AsyncSession] | None = None

    if settings.database_url and (
        repository is None
        or call_record_repository is None
        or appointment_repository is None
        or callback_task_repository is None
        or phone_number_repository is None
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
    if appointment_repository is None:
        if sessions is not None:
            appointment_repository = PostgresAppointmentRepository(sessions)
        else:
            appointment_repository = InMemoryAppointmentRepository()
    if callback_task_repository is None:
        if sessions is not None:
            callback_task_repository = PostgresCallbackTaskRepository(sessions)
        else:
            callback_task_repository = InMemoryCallbackTaskRepository()
    if phone_number_repository is None:
        if sessions is not None:
            phone_number_repository = PostgresPhoneNumberRepository(sessions)
        else:
            phone_number_repository = InMemoryPhoneNumberRepository()
    if scheduling_repository is None:
        if sessions is not None:
            scheduling_repository = PostgresSchedulingRepository(sessions)
        else:
            scheduling_repository = InMemorySchedulingRepository()
    if tool_invocation_repository is None:
        if sessions is not None:
            tool_invocation_repository = PostgresToolInvocationRepository(sessions)
        else:
            tool_invocation_repository = InMemoryToolInvocationRepository()
    if notification_repository is None:
        if sessions is not None:
            notification_repository = PostgresNotificationRepository(sessions)
        else:
            notification_repository = InMemoryNotificationRepository()

    egress_service = RecordingEgressService(
        sink_from_settings(
            endpoint=settings.recording_s3_endpoint,
            bucket=settings.recording_s3_bucket,
            access_key=settings.recording_s3_access_key,
            secret_key=settings.recording_s3_secret_key,
        )
    )
    notification_sink = None
    if settings.smtp_host and settings.smtp_from:
        notification_sink = SmtpNotificationSink(
            host=settings.smtp_host,
            port=settings.smtp_port,
            from_addr=settings.smtp_from,
            username=settings.smtp_username,
            password=settings.smtp_password,
        )
    notification_service = NotificationService(
        notification_repository,
        notification_sink,
    )

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
        allow_methods=["GET", "PUT", "PATCH", "POST", "DELETE"],
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

    app.include_router(
        create_customer_service_router(
            repository,
            token_issuer,
            call_record_repository,
        )
    )
    app.include_router(
        create_call_record_router(
            call_record_repository,
            repository,
            appointments=appointment_repository,
            callbacks=callback_task_repository,
            tools=tool_invocation_repository,
            scheduling=scheduling_repository,
            notifications=notification_service,
            recording_dir=resolved_recording_dir,
            recording_max_bytes=resolved_max_bytes,
        )
    )
    app.include_router(
        create_call_session_router(
            CallLifecycleService(
                call_record_repository,
                repository,
                appointments=appointment_repository,
                callbacks=callback_task_repository,
                tools=tool_invocation_repository,
                scheduling=scheduling_repository,
                notifications=notification_service,
                egress=egress_service,
            )
        )
    )
    app.include_router(
        create_appointment_router(
            appointment_repository,
            repository,
            scheduling_repository,
        )
    )
    app.include_router(
        create_callback_task_router(callback_task_repository, repository)
    )
    app.include_router(
        create_phone_number_router(phone_number_repository, repository)
    )
    app.include_router(
        create_scheduling_router(
            scheduling_repository,
            repository,
            appointment_repository,
        )
    )
    app.include_router(
        create_tool_invocation_router(
            ToolExecutionService(
                tool_invocation_repository,
                appointments=appointment_repository,
                callbacks=callback_task_repository,
                scheduling=scheduling_repository,
                call_records=call_record_repository,
                notifications=notification_service,
            )
        )
    )
    app.include_router(
        create_dashboard_router(
            appointment_repository,
            callback_task_repository,
            call_record_repository,
        )
    )
    app.include_router(create_notification_router(notification_service))

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.state.persistence = (
        "postgres" if sessions is not None else "memory"
    )
    return app


app = create_app()
