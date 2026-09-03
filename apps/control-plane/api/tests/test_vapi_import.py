"""Vapi -> Yino mapping and end-to-end import against the in-memory app."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from yino_platform_api.app import create_app
from yino_platform_api.domain.customer_service import DEMO_TENANT_ID
from yino_platform_api.repositories.appointments import InMemoryAppointmentRepository
from yino_platform_api.repositories.call_records import InMemoryCallRecordRepository
from yino_platform_api.repositories.callback_tasks import InMemoryCallbackTaskRepository
from yino_platform_api.repositories.customer_services import (
    InMemoryCustomerServiceRepository,
)
from yino_platform_api.repositories.phone_numbers import InMemoryPhoneNumberRepository
from yino_platform_api.services.auth import AuthService
from yino_platform_api.vapi_import import (
    ImportState,
    VapiImporter,
    detect_language,
    extract_messages,
    legacy_row_to_call,
    map_assistant,
    map_call,
    map_ended,
    split_overflow,
)

ASSISTANT_EN = {
    "id": "asst-en-1",
    "name": "Front Desk Demo",
    "firstMessage": '"Hi, thanks for calling Demo Clinic. How can I help?"',
    "transcriber": {"provider": "deepgram", "model": "nova-3", "language": "en"},
    "model": {
        "provider": "openai",
        "model": "gpt-4o",
        "toolIds": ["tool-1", "tool-2"],
        "messages": [{"role": "system", "content": "You are the receptionist. " * 20}],
    },
    "voice": {"provider": "11labs", "voiceId": "voice-xyz"},
}

ASSISTANT_ZH = {
    "id": "asst-zh-1",
    "name": "中文前台",
    "firstMessage": "您好，这里是演示机构，请问有什么可以帮您？",
    "transcriber": {
        "provider": "openai",
        "model": "gpt-4o-transcribe",
        "language": "zh",
    },
    "model": {
        "provider": "openai",
        "model": "gpt-4.1",
        "messages": [{"role": "system", "content": "你是前台。"}],
    },
    "voice": {"provider": "minimax", "voiceId": "Wise_Woman"},
}

CALL = {
    "id": "call-1",
    "assistantId": "asst-en-1",
    "type": "inboundPhoneCall",
    "status": "ended",
    "endedReason": "customer-ended-call",
    "createdAt": "2026-08-20T01:00:00.000Z",
    "startedAt": "2026-08-20T01:00:05.000Z",
    "endedAt": "2026-08-20T01:02:35.000Z",
    "customer": {"number": "+61400000099"},
    "phoneNumber": {"number": "+61400000001"},
    "recordingUrl": "https://recordings.example.test/call-1.wav",
    "analysis": {"summary": "Caller asked about opening hours."},
    "artifact": {
        "messages": [
            {"role": "system", "message": "system prompt should be dropped"},
            {"role": "bot", "message": "Hi, thanks for calling."},
            {"role": "user", "message": "What are your opening hours?"},
            {"role": "tool_calls", "message": ""},
            {"role": "bot", "message": "We are open nine to five."},
        ]
    },
}


def test_language_detection_and_default_voice() -> None:
    assert detect_language(ASSISTANT_EN) == "en"
    assert detect_language(ASSISTANT_ZH) == "zh"
    no_lang = {**ASSISTANT_ZH, "transcriber": {}}
    assert detect_language(no_lang) == "zh"
    assert map_assistant(ASSISTANT_EN).create.voice.tts_voice == "loongmary"
    assert map_assistant(ASSISTANT_ZH).create.voice.tts_voice == "longanqian"


def test_map_assistant_cleans_greeting_and_reports_tools_and_voice() -> None:
    mapping = map_assistant(ASSISTANT_EN, voice_map={"voice-xyz": "loongjohn"})
    assert (
        mapping.create.greeting == "Hi, thanks for calling Demo Clinic. How can I help?"
    )
    assert mapping.create.voice.tts_voice == "loongjohn"
    assert mapping.create.tenant_prompt.startswith("You are the receptionist.")
    assert mapping.overflow_prompt is None
    assert any("2 Vapi tool" in warning for warning in mapping.warnings)
    assert not any("mapped to default" in warning for warning in mapping.warnings)


def test_long_prompt_overflows_into_knowledge_chunks() -> None:
    long_prompt = "规则。" * 4000  # 12000 chars
    assistant = {
        **ASSISTANT_ZH,
        "model": {"messages": [{"role": "system", "content": long_prompt}]},
    }
    mapping = map_assistant(assistant)
    assert len(mapping.create.tenant_prompt) == 8000
    assert mapping.overflow_prompt is not None
    assert len(mapping.overflow_prompt) == 4000
    assert all(len(chunk) <= 4000 for chunk in split_overflow(mapping.overflow_prompt))
    assert any("remainder" in warning for warning in mapping.warnings)


def test_ended_reason_mapping() -> None:
    assert map_ended("customer-ended-call") == ("completed", "user_hangup")
    assert map_ended("assistant-ended-call") == ("completed", "completed")
    assert map_ended("assistant-forwarded-call") == ("completed", "completed")
    assert map_ended("silence-timed-out") == ("completed", "completed")
    assert map_ended("pipeline-error-openai-llm-failed") == ("failed", "agent_error")
    assert map_ended(None) == ("completed", "completed")


def test_extract_messages_filters_roles_and_caps() -> None:
    messages, warnings = extract_messages(CALL)
    assert [m.role for m in messages] == ["assistant", "user", "assistant"]
    assert [m.sequence for m in messages] == [0, 1, 2]
    assert warnings == []

    flood = {
        "artifact": {
            "messages": [{"role": "user", "message": f"m{i}"} for i in range(250)]
        }
    }
    capped, capped_warnings = extract_messages(flood)
    assert len(capped) == 200
    assert "transcript capped at 200 messages" in capped_warnings


def test_map_call_fields() -> None:
    instance_id = UUID("00000000-0000-0000-0000-000000000101")
    mapping = map_call(CALL, customer_service_id=instance_id)
    assert mapping is not None
    create = mapping.create
    assert create.room_name == "vapi-call-1"
    assert create.direction == "inbound"
    assert create.status == "completed"
    assert create.ended_reason == "user_hangup"
    assert create.duration_sec == 150
    assert create.caller_number == "+61400000099"
    assert create.callee_number == "+61400000001"
    assert create.provider_call_id == "call-1"
    assert mapping.recording_url == "https://recordings.example.test/call-1.wav"
    assert mapping.summary == "Caller asked about opening hours."
    assert (
        map_call({**CALL, "status": "in-progress"}, customer_service_id=instance_id)
        is None
    )

    withheld = map_call(
        {**CALL, "customer": {"number": "anonymous"}}, customer_service_id=instance_id
    )
    assert withheld is not None
    assert withheld.create.caller_number is None
    assert any("not E.164" in warning for warning in withheld.warnings)


def test_legacy_console_row_maps_like_a_vapi_call() -> None:
    row = {
        "aac_call_id": "legacy-1",
        "aac_assistant_id": "asst-en-1",
        "aac_call_type": "inboundPhoneCall",
        "aac_status": "ended",
        "aac_ended_reason": "assistant-ended-call",
        "aac_customer_number": "+61400000098",
        "aac_started_at": "2026-03-01 10:00:00",
        "aac_ended_at": "2026-03-01 10:01:00",
        "aac_summary": "Legacy summary",
        "aac_recording_url": "https://recordings.example.test/legacy-1.wav",
        "aac_messages": (
            '[{"role": "bot", "message": "Hello"}, {"role": "user", "message": "Hi"}]'
        ),
    }
    call = legacy_row_to_call(row)
    mapping = map_call(
        call, customer_service_id=UUID("00000000-0000-0000-0000-000000000101")
    )
    assert mapping is not None
    # 10:00 at the console's fixed UTC+11 is 23:00 UTC the day before.
    assert mapping.create.started_at.isoformat() == "2026-02-28T23:00:00+00:00"
    assert mapping.create.duration_sec == 60
    assert mapping.create.ended_reason == "completed"
    assert mapping.create.caller_number == "+61400000098"
    assert [m.role for m in mapping.create.messages] == ["assistant", "user"]
    assert mapping.summary == "Legacy summary"
    assert mapping.recording_url.endswith("legacy-1.wav")

    shifted = legacy_row_to_call(row, tz_offset="+08:00")
    assert shifted["startedAt"] == "2026-03-01T10:00:00+08:00"


def _app_client(recording_dir: Path) -> TestClient:
    return TestClient(
        create_app(
            InMemoryCustomerServiceRepository([]),
            call_record_repository=InMemoryCallRecordRepository(),
            appointment_repository=InMemoryAppointmentRepository(),
            callback_task_repository=InMemoryCallbackTaskRepository(),
            phone_number_repository=InMemoryPhoneNumberRepository(),
            auth_service=AuthService(
                secret="s",
                account="demo",
                password="demo123",
                tenant_id=DEMO_TENANT_ID,
                admin_account="root",
                admin_password="root-secret",
            ),
            recording_dir=recording_dir,
        )
    )


def test_end_to_end_import_is_idempotent_and_stores_recordings(tmp_path: Path) -> None:
    client = _app_client(tmp_path / "recordings")
    other_tenant = UUID("00000000-0000-0000-0000-000000000002")
    token = client.post(
        "/api/v1/auth/login", json={"account": "root", "password": "root-secret"}
    ).json()["token"]

    def tenant_for(vapi_id: str) -> UUID:
        return other_tenant if vapi_id == "asst-zh-1" else DEMO_TENANT_ID

    downloads: list[str] = []

    def downloader(url: str) -> tuple[bytes, str]:
        downloads.append(url)
        return b"RIFF....WAVEfmt fake", "audio/wav"

    state_path = tmp_path / "state.json"
    importer = VapiImporter(
        client,
        state=ImportState(state_path),
        tenant_for=tenant_for,
        token=token,
        downloader=downloader,
    )
    importer.ensure_tenants([{"id": str(other_tenant), "name": "Tenant B"}])
    mapping = importer.import_assistants([ASSISTANT_EN, ASSISTANT_ZH])
    assert set(mapping) == {"asst-en-1", "asst-zh-1"}
    importer.import_calls([CALL, {**CALL, "id": "call-2", "assistantId": "unknown"}])
    importer.ensure_users(
        [{"account": "ops-b", "tenant_id": str(other_tenant), "nickname": "B"}]
    )

    statuses = {
        (e["kind"], e.get("vapi_id") or e.get("account")): e["status"]
        for e in importer.report
    }
    assert statuses[("assistant", "asst-en-1")] == "created"
    assert statuses[("call", "call-1")] == "created"
    assert statuses[("call", "call-2")] == "skipped_no_instance"
    assert statuses[("user", "ops-b")] == "created"
    call_entry = next(e for e in importer.report if e.get("vapi_id") == "call-1")
    assert call_entry["recording"] == "stored"
    assert downloads == ["https://recordings.example.test/call-1.wav"]

    demo_headers = {"X-Tenant-ID": str(DEMO_TENANT_ID)}
    records = client.get("/api/v1/call-records", headers=demo_headers).json()
    assert records["total"] == 1
    record = records["items"][0]
    assert record["direction"] == "inbound"
    assert record["recording_status"] == "ready"
    assert record["recording_mime_type"] == "audio/wav"
    assert len(record["messages"]) == 3
    assert (
        client.get(
            "/api/v1/customer-services", headers={"X-Tenant-ID": str(other_tenant)}
        ).json()["total"]
        == 1
    )

    # Second run: nothing is created twice and the state file drives the skips.
    rerun = VapiImporter(
        client,
        state=ImportState(state_path),
        tenant_for=tenant_for,
        token=token,
        downloader=downloader,
    )
    rerun.import_assistants([ASSISTANT_EN, ASSISTANT_ZH])
    rerun.import_calls([CALL])
    assert all(e["status"] == "skipped_existing" for e in rerun.report)
    assert len(downloads) == 1
    assert client.get("/api/v1/call-records", headers=demo_headers).json()["total"] == 1

    login = client.post(
        "/api/v1/auth/login",
        json={
            "account": "ops-b",
            "password": next(
                e["initial_password"] for e in importer.report if e["kind"] == "user"
            ),
        },
    )
    assert login.status_code == 200
    assert login.json()["tenant_id"] == str(other_tenant)


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    client = _app_client(tmp_path / "recordings")
    importer = VapiImporter(
        client,
        state=ImportState(tmp_path / "state.json"),
        tenant_for=lambda _vapi_id: DEMO_TENANT_ID,
        dry_run=True,
    )
    importer.import_assistants([ASSISTANT_EN])
    importer.import_calls([CALL])
    assert {e["status"] for e in importer.report} == {"dry_run"}
    assert all("payload" in e for e in importer.report)
    assert (
        client.get(
            "/api/v1/customer-services", headers={"X-Tenant-ID": str(DEMO_TENANT_ID)}
        ).json()["total"]
        == 0
    )
    assert not (tmp_path / "state.json").exists()
