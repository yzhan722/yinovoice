"""PostgreSQL repository adapters."""

from ..customer_services import CustomerServiceVersionConflict
from .accounts import PostgresTenantRepository, PostgresUserAccountRepository
from .appointments import PostgresAppointmentRepository
from .call_records import PostgresCallRecordRepository
from .callback_tasks import PostgresCallbackTaskRepository
from .config_revisions import PostgresConfigRevisionRepository
from .customer_services import PostgresCustomerServiceRepository
from .insights_dispatch import PostgresInsightsDispatchRepository
from .knowledge import PostgresKnowledgeRepository
from .notifications import PostgresNotificationRepository
from .phone_numbers import PostgresPhoneNumberRepository
from .scheduling import PostgresSchedulingRepository
from .tool_invocations import PostgresToolInvocationRepository

__all__ = [
    "CustomerServiceVersionConflict",
    "PostgresAppointmentRepository",
    "PostgresCallRecordRepository",
    "PostgresCallbackTaskRepository",
    "PostgresConfigRevisionRepository",
    "PostgresCustomerServiceRepository",
    "PostgresInsightsDispatchRepository",
    "PostgresKnowledgeRepository",
    "PostgresNotificationRepository",
    "PostgresPhoneNumberRepository",
    "PostgresSchedulingRepository",
    "PostgresTenantRepository",
    "PostgresToolInvocationRepository",
    "PostgresUserAccountRepository",
]
