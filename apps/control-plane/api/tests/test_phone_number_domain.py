from uuid import uuid4

import pytest
from pydantic import ValidationError

from yino_platform_api.domain.phone_number import (
    PhoneNumber,
    PhoneNumberCreate,
    normalize_e164,
)


def test_normalize_e164_strips_separators() -> None:
    assert normalize_e164("+61 400-000-001") == "+61400000001"
    assert normalize_e164("(+61)400000001") == "+61400000001"


def test_normalize_e164_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match=r"E\.164"):
        normalize_e164("61400000001")
    with pytest.raises(ValueError, match=r"E\.164"):
        normalize_e164("+123")
    with pytest.raises(ValueError, match=r"E\.164"):
        normalize_e164("not-a-number")


def test_phone_number_create_normalizes_and_forbids_server_fields() -> None:
    created = PhoneNumberCreate(
        e164_number="+61 400 000 001",
        voice_agent_instance_id=uuid4(),
    )
    assert created.e164_number == "+61400000001"
    assert created.provider == "livekit_sip"
    assert created.enabled is True
    with pytest.raises(ValidationError):
        PhoneNumberCreate.model_validate(
            {
                "id": str(uuid4()),
                "tenant_id": str(uuid4()),
                "e164_number": "+61400000001",
                "voice_agent_instance_id": str(uuid4()),
            }
        )


def test_phone_number_record_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PhoneNumber.model_validate(
            {
                "id": str(uuid4()),
                "tenant_id": str(uuid4()),
                "voice_agent_instance_id": str(uuid4()),
                "e164_number": "+61400000001",
                "provider": "livekit_sip",
                "enabled": True,
                "created_at": "2026-08-24T00:00:00Z",
                "updated_at": "2026-08-24T00:00:00Z",
                "secret": "nope",
            }
        )
