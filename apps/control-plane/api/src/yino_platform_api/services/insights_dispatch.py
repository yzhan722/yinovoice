from __future__ import annotations

import logging
from uuid import uuid4

from ..domain.call_record import CallRecord
from ..domain.insights_dispatch import InsightsDispatchJob, build_ended_call_body
from ..repositories.customer_services import CustomerServiceRepository
from ..repositories.insights_dispatch import InsightsDispatchRepository

logger = logging.getLogger(__name__)


async def try_enqueue_ended_call(
    record: CallRecord,
    *,
    customer_services: CustomerServiceRepository,
    insights_dispatch: InsightsDispatchRepository | None,
) -> None:
    if insights_dispatch is None:
        return
    try:
        instance = await customer_services.get(
            record.customer_service_id,
            record.tenant_id,
        )
        if instance is None or instance.insights_profile is None:
            return
        if not record.messages:
            return
        body = build_ended_call_body(
            profile=instance.insights_profile,
            record=record,
        )
        await insights_dispatch.enqueue(
            InsightsDispatchJob(
                id=uuid4(),
                tenant_id=record.tenant_id,
                call_id=record.id,
                profile=instance.insights_profile,
                event_id=str(body["eventId"]),
                body=body,
                status="pending",
                attempts=0,
            )
        )
    except Exception:
        logger.exception("insights dispatch enqueue failed")
