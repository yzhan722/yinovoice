# Voice Agent Selection Package Implementation Plan

> 状态：已被 2026-07-29 的大陆区域部署和“通用 Demo 优先”决定部分取代，暂勿直接执行。新的实施计划需以 [新版 PRD](../../prd/voice-agent-platform-prd.md)、[大陆区域部署设计](../specs/2026-07-29-china-regional-deployment-design.md) 和 [通用 Demo 与牙科模板设计](../specs/2026-07-29-generic-demo-dental-template-design.md) 为准；先实施通用 Gate A，再实施牙科 Gate B。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible Python benchmark package that compares commercial Transcriber, Model, and Voice providers for the multilingual dental voice-agent Demo and emits an evidence-labeled recommendation report.

**Architecture:** A provider-neutral core loads a versioned manifest, calls opt-in adapters, records raw timing and outputs, and scores each layer independently. Real providers are enabled only when their environment variables exist; deterministic fake adapters make every workflow testable without credentials.

**Tech Stack:** Python 3.12, `pytest`, `pydantic`, `PyYAML`, `httpx`, `websockets`, `jiwer`, `soundfile`, `pandas`, `jinja2`

## Global Constraints

- Do not train or fine-tune STT, LLM, or TTS models.
- Never commit provider API keys, patient identifiers, or raw production calls.
- Target audio is mono 8 kHz PCM/WAV unless a provider adapter documents another required encoding.
- Demo languages are `zh-CN`, `en-AU`, `en-US`, and `en-GB`, including Mandarin-English code switching.
- Every reported provider result must identify dataset version, adapter version, model name, region, timestamp, and whether the value is measured or sourced.
- Missing credentials produce an explicit `not_run` result, never a synthetic score.
- Provider errors and timeouts are recorded per sample and do not silently disappear from aggregate metrics.

---

### Task 1: Package skeleton and benchmark manifest

**Files:**
- Create: `pyproject.toml`
- Create: `src/voicebench/__init__.py`
- Create: `src/voicebench/schema.py`
- Create: `tests/test_schema.py`
- Create: `benchmarks/demo.yaml`

**Interfaces:**
- Produces: `DatasetManifest`, `AudioSample`, `ProviderRun`, `RunStatus`, and `load_manifest(path: Path) -> DatasetManifest`.
- Consumes: No earlier interfaces.

- [ ] **Step 1: Write schema tests**

```python
from pathlib import Path

import pytest

from voicebench.schema import RunStatus, load_manifest


def test_manifest_loads_supported_locales(tmp_path: Path) -> None:
    manifest = tmp_path / "demo.yaml"
    manifest.write_text(
        "dataset_id: demo-v1\nlocales: [zh-CN, en-AU, en-US, en-GB]\nsamples: []\n",
        encoding="utf-8",
    )
    loaded = load_manifest(manifest)
    assert loaded.dataset_id == "demo-v1"
    assert loaded.locales == ["zh-CN", "en-AU", "en-US", "en-GB"]


def test_unknown_locale_is_rejected(tmp_path: Path) -> None:
    manifest = tmp_path / "bad.yaml"
    manifest.write_text("dataset_id: bad\nlocales: [fr-FR]\nsamples: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported locale"):
        load_manifest(manifest)


def test_not_run_is_a_first_class_status() -> None:
    assert RunStatus.NOT_RUN.value == "not_run"
```

- [ ] **Step 2: Run the tests and verify the import failure**

Run: `python -m pytest tests/test_schema.py -v`
Expected: FAIL because `voicebench.schema` does not exist.

- [ ] **Step 3: Implement the typed schema and YAML loader**

```python
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

Locale = Literal["zh-CN", "en-AU", "en-US", "en-GB"]


class RunStatus(StrEnum):
    MEASURED = "measured"
    NOT_RUN = "not_run"
    FAILED = "failed"


class AudioSample(BaseModel):
    sample_id: str
    locale: Locale
    audio_path: Path
    reference_text: str
    speaker_region: str
    key_fields: dict[str, list[str]] = Field(default_factory=dict)


class DatasetManifest(BaseModel):
    dataset_id: str
    locales: list[Locale]
    samples: list[AudioSample]

    @field_validator("locales", mode="before")
    @classmethod
    def reject_unknown_locales(cls, values: list[str]) -> list[str]:
        allowed = {"zh-CN", "en-AU", "en-US", "en-GB"}
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"Unsupported locale: {sorted(unknown)}")
        return values


class ProviderRun(BaseModel):
    provider: str
    model: str
    region: str
    status: RunStatus
    measured_at: str | None = None
    reason: str | None = None


def load_manifest(path: Path) -> DatasetManifest:
    return DatasetManifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
```

- [ ] **Step 4: Add packaging configuration and an empty versioned manifest**

Create `pyproject.toml` with Python `>=3.12`, the dependencies in the plan header, a `src` package layout, and pytest configured with `pythonpath = ["src"]`. Create `benchmarks/demo.yaml` with dataset ID `dental-demo-v1`, all four locales, and an empty `samples` list so no unlicensed audio is committed.

- [ ] **Step 5: Run the schema tests**

Run: `python -m pytest tests/test_schema.py -v`
Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/voicebench/__init__.py src/voicebench/schema.py tests/test_schema.py benchmarks/demo.yaml
git commit -m "feat: define voice benchmark manifest"
```

### Task 2: Audio validation and privacy-safe ingestion

**Files:**
- Create: `src/voicebench/audio.py`
- Create: `tests/test_audio.py`
- Create: `docs/testing/recording-protocol.md`

**Interfaces:**
- Consumes: `AudioSample` from `voicebench.schema`.
- Produces: `AudioFacts` and `validate_audio(sample: AudioSample) -> AudioFacts`.

- [ ] **Step 1: Write tests for mono 8 kHz validation and identifier rejection**

Use an in-memory generated one-second 8 kHz sine wave and assert `validate_audio` returns `sample_rate_hz == 8000`, `channels == 1`, and `duration_ms == 1000`. Add a manifest sample whose reference contains an 11-digit Chinese mobile number and assert ingestion raises `SensitiveReferenceError` unless the number is one of the documented fictional test numbers.

- [ ] **Step 2: Run the audio tests**

Run: `python -m pytest tests/test_audio.py -v`
Expected: FAIL because `voicebench.audio` does not exist.

- [ ] **Step 3: Implement validation**

Implement `AudioFacts(sample_rate_hz: int, channels: int, duration_ms: int, sha256: str)`, WAV inspection through `soundfile`, a strict mono/8 kHz check, SHA-256 content hashing, and a sensitive-reference check for 11-digit mobile numbers and email addresses. Error messages must name the sample ID without echoing the detected identifier.

- [ ] **Step 4: Write the recording protocol**

Document 4–6 Jiangsu/Zhejiang speakers, consent, fictional patient identities, scripted plus free-form calls, 8 kHz conversion, one transcriber plus one reviewer, immutable reference text, separate key-field labels, and a prohibition on real patient calls.

- [ ] **Step 5: Run the audio tests**

Run: `python -m pytest tests/test_audio.py -v`
Expected: all audio tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/voicebench/audio.py tests/test_audio.py docs/testing/recording-protocol.md
git commit -m "feat: validate benchmark audio ingestion"
```

### Task 3: Provider protocols and deterministic fake adapters

**Files:**
- Create: `src/voicebench/providers/base.py`
- Create: `src/voicebench/providers/fake.py`
- Create: `tests/test_provider_contracts.py`

**Interfaces:**
- Consumes: `AudioSample`, `ProviderRun`, `RunStatus`.
- Produces: `TranscriberAdapter.transcribe`, `ModelAdapter.respond`, `VoiceAdapter.synthesize`, plus typed timing/result records.

- [ ] **Step 1: Write async contract tests**

Create tests asserting the fake Transcriber returns partial and final timestamps, the fake Model records first-token and tool-call data, and the fake Voice returns first-audio and completion timestamps. Add a missing-credential fake and assert its status is exactly `not_run` with no quality score.

- [ ] **Step 2: Run the contract tests**

Run: `python -m pytest tests/test_provider_contracts.py -v`
Expected: FAIL because the provider protocols do not exist.

- [ ] **Step 3: Implement provider protocols**

Define async Python protocols whose result objects always include provider, model, region, status, start time, end time, stage-specific first-result time, raw output reference, and error category. Define tool calls as `{name: str, arguments: dict[str, object]}` and Voice chunks as immutable PCM byte sequences with timestamps.

- [ ] **Step 4: Implement deterministic fake adapters**

Fake adapters must accept fixed scripted outputs and a monotonic fake clock. They must never make network calls and must cover success, timeout, provider error, malformed output, and missing credentials.

- [ ] **Step 5: Run the provider contract tests**

Run: `python -m pytest tests/test_provider_contracts.py -v`
Expected: all provider contract tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/voicebench/providers/base.py src/voicebench/providers/fake.py tests/test_provider_contracts.py
git commit -m "feat: add provider benchmark contracts"
```

### Task 4: Layer-specific metrics

**Files:**
- Create: `src/voicebench/metrics/text.py`
- Create: `src/voicebench/metrics/fields.py`
- Create: `src/voicebench/metrics/timing.py`
- Create: `src/voicebench/metrics/llm.py`
- Create: `tests/test_metrics.py`

**Interfaces:**
- Consumes: reference text, provider hypotheses, key fields, provider timing records, expected tool calls, and policy scenario labels.
- Produces: `SttScore`, `ModelScore`, `VoiceScore`, and normalized metric dictionaries without a cross-provider composite until weights are versioned.

- [ ] **Step 1: Write metric tests with fixed examples**

Test Chinese CER with `预约明天下午三点` versus `预约明天下午四点`, English WER with one substitution, exact and normalized phone/date field matching, first-result latency from monotonic timestamps, exact tool name plus arguments, refusal of disallowed medical diagnosis, and absence of scores for `not_run`.

- [ ] **Step 2: Run the metric tests**

Run: `python -m pytest tests/test_metrics.py -v`
Expected: FAIL because the metric modules do not exist.

- [ ] **Step 3: Implement text and field metrics**

Normalize Unicode width, whitespace, punctuation, spoken digits, and case while preserving the original transcript. Use character error rate for `zh-CN`, word error rate for English, and separate exact/normalized recall for name, phone, date, time, money, and dental-term fields.

- [ ] **Step 4: Implement timing and Model metrics**

Calculate P50/P95 only from measured samples, report the measured count beside every percentile, score tool calls by name and validated arguments, and score safety scenarios as pass/fail. Do not infer safety from keyword overlap alone; scenario fixtures specify the required action type.

- [ ] **Step 5: Run the metric tests**

Run: `python -m pytest tests/test_metrics.py -v`
Expected: all metric tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/voicebench/metrics tests/test_metrics.py
git commit -m "feat: score voice agent provider layers"
```

### Task 5: Benchmark runner and evidence-labeled report

**Files:**
- Create: `src/voicebench/runner.py`
- Create: `src/voicebench/report.py`
- Create: `src/voicebench/cli.py`
- Create: `tests/test_runner.py`
- Create: `tests/test_report.py`
- Create: `benchmarks/scenarios/dental.yaml`

**Interfaces:**
- Consumes: the manifest, provider adapters, layer metrics, and scenario definitions.
- Produces: `python -m voicebench.cli run ...`, versioned JSON run artifacts, and a Markdown report that separates measured, official-source, and unavailable evidence.

- [ ] **Step 1: Write end-to-end fake-run tests**

Run a two-sample manifest through fake Transcriber, Model, and Voice adapters. Assert the JSON artifact contains dataset hash, adapter versions, model IDs, region, timestamps, raw stage timings, errors, and metrics. Assert the Markdown report labels fake results as measured fixtures rather than vendor evidence.

- [ ] **Step 2: Run the runner/report tests**

Run: `python -m pytest tests/test_runner.py tests/test_report.py -v`
Expected: FAIL because runner and report modules do not exist.

- [ ] **Step 3: Implement bounded concurrent execution**

Use `asyncio.TaskGroup` plus a semaphore configured by CLI argument. Persist one JSON line per sample immediately, resume by sample/provider/model key, apply per-stage timeouts, and redact configured secrets from errors before writing artifacts.

- [ ] **Step 4: Implement report generation**

Generate separate Transcriber, Model, and Voice tables; include P50/P95 and sample counts; list failures; show cost assumptions; label each cell `measured`, `official_source`, or `not_run`; and block ranking when candidates were evaluated on different dataset hashes.

- [ ] **Step 5: Add dental scenarios and CLI**

Define scenarios for FAQ fidelity, appointment confirmation, tool failure, emergency handoff, prompt injection, identity verification, interruption, Mandarin-English switching, and authorized follow-up. The CLI exposes `validate`, `run`, and `report` subcommands with explicit input and output paths.

- [ ] **Step 6: Run all tests**

Run: `python -m pytest -v`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/voicebench/runner.py src/voicebench/report.py src/voicebench/cli.py tests/test_runner.py tests/test_report.py benchmarks/scenarios/dental.yaml
git commit -m "feat: run and report voice benchmarks"
```

### Task 6: Alibaba baseline adapters after credentials are configured

**Files:**
- Create: `src/voicebench/providers/aliyun_fun_asr.py`
- Create: `src/voicebench/providers/qwen_model.py`
- Create: `src/voicebench/providers/qwen_voice.py`
- Create: `tests/providers/test_aliyun_fun_asr.py`
- Create: `tests/providers/test_qwen_model.py`
- Create: `tests/providers/test_qwen_voice.py`
- Create: `benchmarks/providers/aliyun-beijing.yaml`
- Create: `docs/testing/provider-credentials.md`

**Interfaces:**
- Consumes: provider protocols from Task 3 and the shortlist in `docs/research/model-provider-research.md`.
- Produces: opt-in adapters for `fun-asr-realtime`/`fun-asr-flash-8k-realtime`, `qwen-plus`, and `qwen3-tts-flash-realtime`, configured for the documented Beijing endpoints.

- [ ] **Step 1: Document regional credentials and exact baseline configuration**

Document `DASHSCOPE_API_KEY`, `DASHSCOPE_WORKSPACE_ID`, and the Beijing HTTP/WebSocket base URLs without secret values. In `benchmarks/providers/aliyun-beijing.yaml`, set Transcriber models to `fun-asr-realtime` and `fun-asr-flash-8k-realtime`, Model to `qwen-plus`, Voice model to `qwen3-tts-flash-realtime`, and Voice ID to `Cherry`. The file must label the region `cn-beijing`; Singapore is a separate future profile because its model set and API key differ.

- [ ] **Step 2: Write mocked transport contract tests**

For each adapter, mock the provider HTTP or WebSocket transport and assert authentication headers, 8 kHz audio declaration, locale, hotwords, streaming event parsing, timeout classification, usage capture, and secret redaction. Model tests must cover streaming tool calls; Voice tests must cover first-audio timing and cancellation.

- [ ] **Step 3: Run the mocked tests**

Run: `python -m pytest tests/providers -v`
Expected: FAIL because the Alibaba adapters do not exist.

- [ ] **Step 4: Implement the three adapters**

Implement only the documented request and event fields used by the benchmark contract. Read credentials exclusively from `DASHSCOPE_API_KEY` and `DASHSCOPE_WORKSPACE_ID`, return `not_run` when absent, and preserve provider request IDs for support without logging secrets or patient content. Record Qwen Voice's native 24 kHz PCM output before deterministic 8 kHz telephony conversion so both stages can be measured.

- [ ] **Step 5: Run mocked and opt-in smoke tests**

Run: `python -m pytest tests/providers -v`
Expected: all mocked tests pass. With credentials absent, live smoke tests are skipped with a reason; with credentials present, one fictional sample per layer completes and writes a measured artifact.

- [ ] **Step 6: Generate the first real report**

Run: `python -m voicebench.cli validate benchmarks/demo.yaml`
Expected: the corpus passes audio, locale, reference, and sensitive-data validation.

Run: `python -m voicebench.cli run benchmarks/demo.yaml --providers aliyun_fun_asr,qwen_model,qwen_voice --concurrency 4 --output artifacts/run-001.jsonl`
Expected: every configured candidate has measured or explicit failed status; no candidate is silently skipped.

Run: `python -m voicebench.cli report artifacts/run-001.jsonl --output artifacts/run-001.md`
Expected: a Markdown report with comparable dataset hashes and separated layer tables.

- [ ] **Step 7: Commit**

```bash
git add src/voicebench/providers tests/providers docs/testing/provider-credentials.md
git commit -m "feat: add initial commercial provider adapters"
```

### Task 7: Cross-provider comparison adapters

**Files:**
- Create: `src/voicebench/providers/tencent_asr.py`
- Create: `src/voicebench/providers/deepgram_asr.py`
- Create: `src/voicebench/providers/azure_speech.py`
- Create: `src/voicebench/providers/openai_model.py`
- Create: `src/voicebench/providers/gemini_model.py`
- Create: `src/voicebench/providers/elevenlabs_voice.py`
- Create: `tests/providers/test_tencent_asr.py`
- Create: `tests/providers/test_deepgram_asr.py`
- Create: `tests/providers/test_azure_speech.py`
- Create: `tests/providers/test_openai_model.py`
- Create: `tests/providers/test_gemini_model.py`
- Create: `tests/providers/test_elevenlabs_voice.py`
- Create: `benchmarks/providers/comparison-wave-1.yaml`

**Interfaces:**
- Consumes: provider protocols, credential rules, corpus, metrics, and runner from Tasks 1–6.
- Produces: the first cross-provider comparison group: Tencent and Deepgram Transcriber, Azure Transcriber/Voice, OpenAI and Gemini Model, and ElevenLabs Voice.

- [ ] **Step 1: Define the exact comparison configuration**

Create `comparison-wave-1.yaml` with Tencent's documented 8 kHz real-time engine selected after console entitlement check, Deepgram `nova-3` with separate `zh-CN`, `en-AU`, `en-US`, and `en-GB` runs, Azure Speech locales for the same four values, one pinned OpenAI model snapshot supporting streaming tool calls and Structured Outputs, one pinned Gemini model supporting streaming function calling, and ElevenLabs `eleven_flash_v2_5` with one licensed preset Voice per target locale. Record any unavailable model as disabled with an evidence-backed reason, not by substituting another silently.

- [ ] **Step 2: Write mocked transport tests for every adapter**

Assert provider-specific authentication, locale/engine selection, 8 kHz declaration or deterministic conversion, Domain Pack mapping, partial/final event parsing, tool-call assembly, first-audio timing, cancellation, provider request IDs, usage capture, timeout/error normalization, and secret redaction. Credential variables are `TENCENTCLOUD_SECRET_ID`, `TENCENTCLOUD_SECRET_KEY`, `TENCENTCLOUD_APP_ID`, `DEEPGRAM_API_KEY`, `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, and `ELEVENLABS_API_KEY`.

- [ ] **Step 3: Run comparison adapter tests before implementation**

Run: `python -m pytest tests/providers/test_tencent_asr.py tests/providers/test_deepgram_asr.py tests/providers/test_azure_speech.py tests/providers/test_openai_model.py tests/providers/test_gemini_model.py tests/providers/test_elevenlabs_voice.py -v`
Expected: FAIL because the comparison adapters do not exist.

- [ ] **Step 4: Implement the comparison adapters**

Use the provider's documented HTTP/WebSocket protocol and map every response to the Task 3 contracts. Adapters return `not_run` with the missing variable names when credentials are absent. Azure exposes distinct Transcriber and Voice objects from one module; it must not share mutable session state between concurrent calls.

- [ ] **Step 5: Run mocked tests and credential-gated smoke tests**

Run: `python -m pytest tests/providers -v`
Expected: all mocked tests pass; each live smoke test is skipped with a reason when its credential set is absent and completes one fictional sample when configured.

- [ ] **Step 6: Run the comparison on a frozen dataset**

Run: `python -m voicebench.cli run benchmarks/demo.yaml --provider-config benchmarks/providers/comparison-wave-1.yaml --concurrency 4 --output artifacts/comparison-wave-1.jsonl`
Expected: every enabled provider/sample pair has `measured` or `failed` status, and every disabled or uncredentialed provider has `not_run` status.

Run: `python -m voicebench.cli report artifacts/comparison-wave-1.jsonl --output artifacts/comparison-wave-1.md`
Expected: separate Transcriber, Model, and Voice tables; no ranking across different dataset hashes; quality, latency, reliability, and cost shown together.

- [ ] **Step 7: Commit**

```bash
git add src/voicebench/providers tests/providers benchmarks/providers/comparison-wave-1.yaml docs/testing/provider-credentials.md
git commit -m "feat: compare commercial voice agent providers"
```

## Self-Review Result

- Spec coverage: the plan covers dataset governance, all three model layers, four locales, key-field metrics, latency, tool and safety scenarios, provider failure handling, evidence labeling, an Alibaba baseline, and a cross-provider credential-gated comparison.
- Placeholder scan: provider filenames, credential names, initial model IDs, commands, expected outcomes, and failure behavior are explicit; no implementation behavior is deferred.
- Type consistency: all later tasks consume the manifest and provider result types introduced in Tasks 1 and 3; metric and report layers operate on explicit statuses and never create scores for `not_run`.
