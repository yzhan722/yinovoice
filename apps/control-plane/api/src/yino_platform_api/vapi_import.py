"""Map Vapi assistants and calls onto Yino Platform API payloads (plan P1.4).

Pure mapping helpers live at module level so they can be unit-tested with
synthetic fixtures; ``VapiImporter`` drives an ``httpx.Client`` (a FastAPI
``TestClient`` works too) against the Platform API and keeps an idempotency
state file so re-runs skip what already landed.
"""

from __future__ import annotations

import json
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx

from .domain.call_record import (
    CallRecordCreate,
    EndedCallRecordStatus,
    EndedReason,
    TranscriptMessage,
)
from .domain.customer_service import (
    CustomerServiceCreate,
    TtsVoiceId,
    VoiceProfile,
)

TENANT_PROMPT_LIMIT = 8000
GREETING_LIMIT = 300
KNOWLEDGE_BODY_LIMIT = 4000
TRANSCRIPT_TEXT_LIMIT = 4000
TRANSCRIPT_MAX_MESSAGES = 200

_CJK = re.compile(r"[\u4e00-\u9fff]")
_E164 = re.compile(r"^\+[1-9]\d{7,14}$")
_DEFAULT_VOICE: dict[str, TtsVoiceId] = {"zh": "longanqian", "en": "loongmary"}
_ROLE_MAP = {"bot": "assistant", "assistant": "assistant", "user": "user"}


@dataclass
class AssistantMapping:
    vapi_id: str
    name: str
    language: str
    create: CustomerServiceCreate
    overflow_prompt: str | None
    warnings: list[str] = field(default_factory=list)


@dataclass
class CallMapping:
    vapi_id: str
    assistant_id: str | None
    create: CallRecordCreate
    recording_url: str | None
    summary: str | None
    warnings: list[str] = field(default_factory=list)


def detect_language(assistant: dict[str, Any]) -> str:
    transcriber = assistant.get("transcriber") or {}
    language = str(transcriber.get("language") or "").lower()
    if language.startswith("zh"):
        return "zh"
    if language.startswith("en"):
        return "en"
    text = " ".join(
        [str(assistant.get("firstMessage") or ""), _system_prompt(assistant)[:400]]
    )
    return "zh" if _CJK.search(text) else "en"


def default_voice_for(language: str) -> TtsVoiceId:
    return _DEFAULT_VOICE.get(language, "longanqian")


def _system_prompt(assistant: dict[str, Any]) -> str:
    model = assistant.get("model") or {}
    parts = [
        str(message.get("content") or "")
        for message in model.get("messages") or []
        if message.get("role") == "system"
    ]
    return "\n\n".join(part.strip() for part in parts if part.strip())


def _clean_greeting(raw: str | None, fallback: str) -> str:
    greeting = (raw or "").strip().strip('"“”').strip()
    return (greeting or fallback)[:GREETING_LIMIT]


def _clip(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[:limit]


def map_assistant(
    assistant: dict[str, Any],
    *,
    voice_map: dict[str, str] | None = None,
) -> AssistantMapping:
    vapi_id = str(assistant.get("id") or "")
    if not vapi_id:
        raise ValueError("assistant without id")
    name = (assistant.get("name") or f"Vapi assistant {vapi_id[:8]}").strip()
    language = detect_language(assistant)
    warnings: list[str] = []

    prompt = _system_prompt(assistant)
    overflow: str | None = None
    if len(prompt) > TENANT_PROMPT_LIMIT:
        overflow = prompt[TENANT_PROMPT_LIMIT:]
        prompt = prompt[:TENANT_PROMPT_LIMIT]
        warnings.append(
            f"system prompt is {len(prompt) + len(overflow)} chars; "
            f"first {TENANT_PROMPT_LIMIT} kept in tenant_prompt, remainder "
            "stored as knowledge documents (not applied)"
        )

    voice = assistant.get("voice") or {}
    vapi_voice = f"{voice.get('provider') or '?'}/{voice.get('voiceId') or '?'}"
    tts_voice = default_voice_for(language)
    mapped = (voice_map or {}).get(str(voice.get("voiceId") or ""))
    if mapped:
        tts_voice = mapped  # type: ignore[assignment]
    else:
        warnings.append(f"voice {vapi_voice} mapped to default {tts_voice}")

    tools = (assistant.get("model") or {}).get("toolIds") or []
    if tools:
        warnings.append(
            f"{len(tools)} Vapi tool(s) not imported; re-create as Yino tools"
        )

    fallback_greeting = (
        "您好，请问有什么可以帮您？"
        if language == "zh"
        else "Hello, how can I help you today?"
    )
    create = CustomerServiceCreate(
        display_name=_clip(name, 80),
        organization_name=_clip(name, 120),
        greeting=_clean_greeting(assistant.get("firstMessage"), fallback_greeting),
        platform_prompt="",
        tenant_prompt=prompt,
        voice=VoiceProfile(tts_voice=tts_voice),
    )
    return AssistantMapping(
        vapi_id=vapi_id,
        name=name,
        language=language,
        create=create,
        overflow_prompt=overflow,
        warnings=warnings,
    )


def split_overflow(overflow: str) -> list[str]:
    return [
        overflow[index : index + KNOWLEDGE_BODY_LIMIT]
        for index in range(0, len(overflow), KNOWLEDGE_BODY_LIMIT)
    ]


def map_ended(reason: str | None) -> tuple[EndedCallRecordStatus, EndedReason]:
    value = (reason or "").lower()
    if "error" in value or "failed" in value:
        return "failed", "agent_error"
    if value.startswith("customer-ended") or "customer-did-not" in value:
        return "completed", "user_hangup"
    return "completed", "completed"


def e164_or_none(value: Any) -> str | None:
    """Vapi reports withheld caller ids as 'anonymous'; keep only real E.164."""
    if not value:
        return None
    candidate = re.sub(r"[\s\-().]", "", str(value))
    return candidate if _E164.match(candidate) else None


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    # Platform payloads must be UTC; legacy rows arrive with a fixed offset.
    return parsed.astimezone(UTC)


def extract_messages(call: dict[str, Any]) -> tuple[list[TranscriptMessage], list[str]]:
    raw = (call.get("artifact") or {}).get("messages") or call.get("messages") or []
    messages: list[TranscriptMessage] = []
    warnings: list[str] = []
    for item in raw:
        role = _ROLE_MAP.get(str(item.get("role") or ""))
        text = str(item.get("message") or item.get("content") or "").strip()
        if role is None or not text:
            continue
        if len(text) > TRANSCRIPT_TEXT_LIMIT:
            text = text[:TRANSCRIPT_TEXT_LIMIT]
            warnings.append("transcript message truncated to 4000 chars")
        messages.append(
            TranscriptMessage(role=role, text=text, sequence=len(messages))  # type: ignore[arg-type]
        )
        if len(messages) >= TRANSCRIPT_MAX_MESSAGES:
            warnings.append("transcript capped at 200 messages")
            break
    return messages, warnings


def map_call(call: dict[str, Any], *, customer_service_id: UUID) -> CallMapping | None:
    vapi_id = str(call.get("id") or "")
    if not vapi_id or call.get("status") != "ended":
        return None
    started = _parse_time(call.get("startedAt") or call.get("createdAt"))
    ended = _parse_time(call.get("endedAt") or call.get("updatedAt"))
    if started is None:
        return None
    if ended is None or ended < started:
        ended = started
    duration = min(int((ended - started).total_seconds()), 86_400)

    status, ended_reason = map_ended(call.get("endedReason"))
    messages, warnings = extract_messages(call)
    call_type = str(call.get("type") or "")
    if call_type == "outboundPhoneCall":
        direction = "outbound"
    elif call_type == "webCall":
        direction = "web"
    else:
        direction = "inbound"
    if str(call.get("endedReason") or "").startswith("assistant-forwarded"):
        warnings.append(
            "call was forwarded to a human on Vapi (no Yino equivalent yet)"
        )
    raw_caller = (call.get("customer") or {}).get("number")
    caller_number = e164_or_none(raw_caller)
    if raw_caller and caller_number is None:
        warnings.append(f"caller id not E.164 ({raw_caller!s}); stored as unknown")
    callee_number = e164_or_none((call.get("phoneNumber") or {}).get("number"))

    create = CallRecordCreate(
        customer_service_id=customer_service_id,
        room_name=f"vapi-{vapi_id}"[:128],
        status=status,
        started_at=started,
        connected_at=started,
        ended_at=ended,
        duration_sec=duration,
        direction=direction,  # type: ignore[arg-type]
        caller_number=caller_number,
        callee_number=callee_number,
        provider_call_id=vapi_id,
        ended_reason=ended_reason,
        messages=messages,
    )
    analysis = call.get("analysis") or {}
    return CallMapping(
        vapi_id=vapi_id,
        assistant_id=call.get("assistantId"),
        create=create,
        recording_url=call.get("recordingUrl")
        or (call.get("artifact") or {}).get("recordingUrl"),
        summary=analysis.get("summary") or call.get("summary"),
        warnings=warnings,
    )


def _with_offset(value: Any, offset: str) -> Any:
    """Legacy MySQL DATETIME columns carry no zone; the console's JDBC URL fixed
    them to a UTC offset, so re-attach it unless the value already has one."""
    if not value:
        return value
    text = str(value).strip().replace(" ", "T")
    if text.endswith("Z") or re.search(r"[+-]\d{2}:\d{2}$", text):
        return text
    return f"{text}{offset}"


def legacy_row_to_call(
    row: dict[str, Any], *, tz_offset: str = "+11:00"
) -> dict[str, Any]:
    """Convert an ``ai_assistant_call`` row from the legacy MySQL console into
    the Vapi call shape ``map_call`` understands.

    Vapi's list API only returns recent calls; the legacy console synced every
    call since launch, so its export is the source for history.
    """
    messages = row.get("aac_messages")
    if isinstance(messages, str):
        try:
            messages = json.loads(messages)
        except ValueError:
            messages = []
    status = str(row.get("aac_status") or "ended")
    return {
        "id": row.get("aac_call_id"),
        "assistantId": row.get("aac_assistant_id"),
        "phoneNumberId": row.get("aac_phone_number_id"),
        "type": row.get("aac_call_type") or "inboundPhoneCall",
        "status": "ended" if status in ("ended", "completed") else status,
        "endedReason": row.get("aac_ended_reason"),
        "createdAt": _with_offset(
            row.get("aac_created_at") or row.get("aac_started_at"), tz_offset
        ),
        "startedAt": _with_offset(row.get("aac_started_at"), tz_offset),
        "endedAt": _with_offset(row.get("aac_ended_at"), tz_offset),
        "customer": {"number": row.get("aac_customer_number")},
        "recordingUrl": row.get("aac_recording_url"),
        "analysis": {"summary": row.get("aac_summary")},
        "artifact": {"messages": messages or []},
    }


class ImportState:
    """vapi id -> yino id maps persisted between runs."""

    def __init__(self, path: Path | None) -> None:
        self._path = path
        self.assistants: dict[str, str] = {}
        self.calls: dict[str, str] = {}
        self.recordings: dict[str, str] = {}
        if path is not None and path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assistants = dict(data.get("assistants") or {})
            self.calls = dict(data.get("calls") or {})
            self.recordings = dict(data.get("recordings") or {})

    def save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(
                {
                    "assistants": self.assistants,
                    "calls": self.calls,
                    "recordings": self.recordings,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


Downloader = Callable[[str], tuple[bytes, str]]


class VapiImporter:
    def __init__(
        self,
        api: httpx.Client,
        *,
        state: ImportState,
        tenant_for: Callable[[str], UUID],
        token: str | None = None,
        dry_run: bool = False,
        voice_map: dict[str, str] | None = None,
        downloader: Downloader | None = None,
    ) -> None:
        self._api = api
        self._state = state
        self._tenant_for = tenant_for
        self._token = token
        self._dry_run = dry_run
        self._voice_map = voice_map
        self._downloader = downloader
        self.report: list[dict[str, Any]] = []

    def _headers(self, tenant_id: UUID) -> dict[str, str]:
        headers = {"X-Tenant-ID": str(tenant_id)}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _post(self, path: str, tenant_id: UUID, **kwargs: Any) -> httpx.Response:
        response = self._api.post(path, headers=self._headers(tenant_id), **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(
                f"{path} -> {response.status_code}: {response.text[:300]}"
            )
        return response

    # -- assistants -------------------------------------------------------
    def import_assistants(self, assistants: list[dict[str, Any]]) -> dict[str, str]:
        for assistant in assistants:
            mapping = map_assistant(assistant, voice_map=self._voice_map)
            tenant_id = self._tenant_for(mapping.vapi_id)
            entry: dict[str, Any] = {
                "kind": "assistant",
                "vapi_id": mapping.vapi_id,
                "name": mapping.name,
                "tenant_id": str(tenant_id),
                "language": mapping.language,
                "warnings": list(mapping.warnings),
            }
            if mapping.vapi_id in self._state.assistants:
                entry["status"] = "skipped_existing"
                entry["instance_id"] = self._state.assistants[mapping.vapi_id]
                self.report.append(entry)
                continue
            if self._dry_run:
                entry["status"] = "dry_run"
                entry["payload"] = mapping.create.model_dump(mode="json")
                # Placeholder so the call preview can resolve its instance;
                # dry runs never persist the state file.
                self._state.assistants[mapping.vapi_id] = str(
                    uuid5(NAMESPACE_URL, f"vapi-dry-run:{mapping.vapi_id}")
                )
                self.report.append(entry)
                continue
            created = self._post(
                "/api/v1/customer-services",
                tenant_id,
                json=mapping.create.model_dump(mode="json"),
            ).json()
            instance_id = str(created["id"])
            self._state.assistants[mapping.vapi_id] = instance_id
            if mapping.overflow_prompt:
                chunks = split_overflow(mapping.overflow_prompt)
                for index, chunk in enumerate(chunks, start=1):
                    self._post(
                        f"/api/v1/customer-services/{instance_id}/knowledge",
                        tenant_id,
                        json={
                            "title": f"Vapi 提示词（续 {index}/{len(chunks)}）",
                            "body": chunk,
                        },
                    )
                entry["overflow_chunks"] = len(chunks)
            entry["status"] = "created"
            entry["instance_id"] = instance_id
            self.report.append(entry)
            self._state.save()
        return dict(self._state.assistants)

    # -- calls ------------------------------------------------------------
    def import_calls(self, calls: list[dict[str, Any]]) -> None:
        for call in calls:
            assistant_id = str(call.get("assistantId") or "")
            instance_id = self._state.assistants.get(assistant_id)
            entry: dict[str, Any] = {
                "kind": "call",
                "vapi_id": call.get("id"),
                "assistant_id": assistant_id,
            }
            if instance_id is None:
                entry["status"] = "skipped_no_instance"
                self.report.append(entry)
                continue
            mapping = map_call(call, customer_service_id=UUID(instance_id))
            if mapping is None:
                entry["status"] = "skipped_not_ended"
                self.report.append(entry)
                continue
            entry["warnings"] = list(mapping.warnings)
            entry["summary"] = mapping.summary
            tenant_id = self._tenant_for(assistant_id)
            if mapping.vapi_id in self._state.calls:
                entry["status"] = "skipped_existing"
                entry["record_id"] = self._state.calls[mapping.vapi_id]
            elif self._dry_run:
                entry["status"] = "dry_run"
                entry["payload"] = mapping.create.model_dump(mode="json")
            else:
                created = self._post(
                    "/api/v1/call-records",
                    tenant_id,
                    json=mapping.create.model_dump(mode="json"),
                ).json()
                self._state.calls[mapping.vapi_id] = str(created["id"])
                entry["status"] = "created"
                entry["record_id"] = created["id"]
                self._state.save()
            record_id = self._state.calls.get(mapping.vapi_id)
            if (
                record_id
                and mapping.recording_url
                and self._downloader is not None
                and not self._dry_run
                and mapping.vapi_id not in self._state.recordings
            ):
                entry["recording"] = self._upload_recording(
                    tenant_id, record_id, mapping.vapi_id, mapping.recording_url
                )
            self.report.append(entry)

    def _upload_recording(
        self, tenant_id: UUID, record_id: str, vapi_id: str, url: str
    ) -> str:
        assert self._downloader is not None
        try:
            content, mime = self._downloader(url)
        except Exception as error:  # report per call and keep importing
            return f"download_failed: {error}"
        suffix = ".mp3" if "mpeg" in mime else ".wav"
        response = self._api.post(
            f"/api/v1/call-records/{record_id}/recording",
            headers=self._headers(tenant_id),
            files={"file": (f"{vapi_id}{suffix}", content, mime)},
        )
        if response.status_code >= 400:
            return f"upload_failed: {response.status_code} {response.text[:200]}"
        self._state.recordings[vapi_id] = record_id
        self._state.save()
        return "stored"

    # -- tenants / users --------------------------------------------------
    def ensure_tenants(self, tenants: list[dict[str, Any]]) -> None:
        """Create tenants via the admin API (requires a platform_admin token)."""
        if not self._token:
            raise RuntimeError("ensure_tenants requires an admin token")
        existing = {
            item["id"]
            for item in self._api.get(
                "/api/v1/admin/tenants",
                headers={"Authorization": f"Bearer {self._token}"},
            ).json()["items"]
        }
        for tenant in tenants:
            entry = {
                "kind": "tenant",
                "tenant_id": tenant["id"],
                "name": tenant["name"],
            }
            if tenant["id"] in existing:
                entry["status"] = "skipped_existing"
            elif self._dry_run:
                entry["status"] = "dry_run"
            else:
                self._api.post(
                    "/api/v1/admin/tenants",
                    headers={"Authorization": f"Bearer {self._token}"},
                    json={
                        "id": tenant["id"],
                        "name": tenant["name"],
                        "home_region": tenant.get("home_region", "cn-mainland"),
                    },
                ).raise_for_status()
                entry["status"] = "created"
            self.report.append(entry)

    def ensure_users(self, users: list[dict[str, Any]]) -> None:
        """Create operator accounts; generated passwords are written to the report."""
        if not self._token:
            raise RuntimeError("ensure_users requires an admin token")
        for user in users:
            password = user.get("password") or secrets.token_urlsafe(12)
            entry = {
                "kind": "user",
                "account": user["account"],
                "tenant_id": user["tenant_id"],
                "status": "dry_run" if self._dry_run else "created",
            }
            if not self._dry_run:
                response = self._api.post(
                    "/api/v1/admin/users",
                    headers={"Authorization": f"Bearer {self._token}"},
                    json={
                        "tenant_id": user["tenant_id"],
                        "account": user["account"],
                        "password": password,
                        "nickname": user.get("nickname") or user["account"],
                        "role": user.get("role", "tenant_operator"),
                    },
                )
                if response.status_code == 409:
                    entry["status"] = "skipped_existing"
                    self.report.append(entry)
                    continue
                response.raise_for_status()
            entry["initial_password"] = password
            self.report.append(entry)
