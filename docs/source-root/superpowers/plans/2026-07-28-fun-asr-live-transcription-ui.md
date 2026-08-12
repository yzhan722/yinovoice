# Fun-ASR Live Transcription UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local browser workbench that captures microphone audio, streams 16 kHz PCM16 to a Python backend, and displays Alibaba Cloud Fun-ASR partial and final transcripts in real time.

**Architecture:** A FastAPI application serves a framework-free HTML/CSS/JavaScript frontend and exposes one WebSocket endpoint per transcription session. The browser converts microphone audio to 100 ms PCM16 chunks; a provider-neutral session controller forwards those chunks to a Beijing-region Fun-ASR adapter and maps SDK callbacks into stable browser events.

**Tech Stack:** Python 3.12+, FastAPI, Uvicorn, DashScope Python SDK 1.23.1+, Pydantic 2, pytest, pytest-asyncio, vanilla ES modules, Web Audio API, AudioWorklet, Node.js built-in test runner.

## Global Constraints

- Region is fixed to `cn-beijing` for this prototype.
- Read credentials only from `DASHSCOPE_API_KEY` and `DASHSCOPE_WORKSPACE_ID`.
- Use `wss://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference`.
- Browser audio is mono, 16 kHz, signed 16-bit little-endian PCM, sent in approximately 100 ms chunks.
- Use VAD segmentation with `semantic_punctuation_enabled=False` and default `max_sentence_silence=1000` ms.
- Do not store raw audio or transcripts and do not log patient content or credentials.
- Partial transcript events replace the current partial text; final events append exactly one sentence.
- The current directory is not a Git repository. Commit steps below are intended checkpoints and must be skipped unless the user initializes or supplies a Git repository.

---

## File Structure

- `pyproject.toml`: Python package metadata, runtime dependencies, pytest configuration, and `voice-stt` development command.
- `package.json`: dependency-free Node test command for pure frontend state modules.
- `.env.example`: non-secret names for required environment configuration.
- `src/voice_stt/__init__.py`: package marker.
- `src/voice_stt/config.py`: validates Beijing-region environment configuration and constructs the business-space WebSocket URL.
- `src/voice_stt/protocol.py`: typed client messages, server events, and stable error codes.
- `src/voice_stt/transcriber.py`: provider-neutral transcriber session and factory protocols.
- `src/voice_stt/aliyun_fun_asr.py`: DashScope `Recognition` adapter and callback-to-event bridge.
- `src/voice_stt/session.py`: browser WebSocket state machine and provider event forwarding.
- `src/voice_stt/app.py`: FastAPI application factory, static assets, health endpoint, and WebSocket route.
- `src/voice_stt/__main__.py`: local Uvicorn entry point.
- `src/voice_stt/static/index.html`: accessible single-page workbench structure.
- `src/voice_stt/static/styles.css`: responsive visual system and state styling.
- `src/voice_stt/static/transcript-state.js`: pure transcript state reducer shared by UI and Node tests.
- `src/voice_stt/static/pcm-worklet.js`: microphone resampling, PCM16 encoding, 100 ms chunking, and input level messages.
- `src/voice_stt/static/app.js`: microphone lifecycle, WebSocket client, renderer, download/copy/clear actions, and error recovery.
- `tests/test_config.py`: credential and endpoint configuration tests.
- `tests/test_protocol.py`: client-message parsing and server-event serialization tests.
- `tests/test_aliyun_fun_asr.py`: mocked SDK adapter contract tests.
- `tests/test_session.py`: WebSocket session ordering and error tests with a fake transcriber.
- `tests/test_app.py`: health and static asset smoke tests.
- `tests/frontend/transcript-state.test.mjs`: partial/final reducer tests.
- `tests/frontend/pcm-worklet.test.mjs`: deterministic resampling/chunk-size tests through exported pure helpers.
- `README.md`: setup, credential, run, test, privacy, and troubleshooting instructions.

---

### Task 1: Project Configuration and Typed Protocol

**Files:**
- Create: `pyproject.toml`
- Create: `package.json`
- Create: `.env.example`
- Create: `src/voice_stt/__init__.py`
- Create: `src/voice_stt/config.py`
- Create: `src/voice_stt/protocol.py`
- Test: `tests/test_config.py`
- Test: `tests/test_protocol.py`

**Interfaces:**
- Produces: `Settings.from_env() -> Settings`, `Settings.websocket_url -> str`.
- Produces: `StartMessage`, `StopMessage`, `parse_control_message(raw: str) -> StartMessage | StopMessage`.
- Produces: `SessionStarted`, `TranscriptPartial`, `TranscriptFinal`, `SessionMetric`, `SessionCompleted`, and `SessionError` with `to_json() -> str`.
- Consumes: no earlier task interfaces.

- [ ] **Step 1: Write failing configuration tests**

```python
# tests/test_config.py
import pytest

from voice_stt.config import ConfigurationError, Settings


def test_settings_build_beijing_workspace_url() -> None:
    settings = Settings(api_key="key", workspace_id="ws-123")
    assert settings.region == "cn-beijing"
    assert settings.websocket_url == (
        "wss://ws-123.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"
    )


def test_missing_credentials_list_environment_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_WORKSPACE_ID", raising=False)
    with pytest.raises(ConfigurationError) as error:
        Settings.from_env()
    assert error.value.missing == (
        "DASHSCOPE_API_KEY",
        "DASHSCOPE_WORKSPACE_ID",
    )
```

- [ ] **Step 2: Write failing protocol tests**

```python
# tests/test_protocol.py
import json

import pytest
from pydantic import ValidationError

from voice_stt.protocol import (
    StartMessage,
    TranscriptFinal,
    parse_control_message,
)


def test_start_message_applies_interaction_defaults() -> None:
    message = parse_control_message(
        '{"type":"start","sampleRate":16000,"language":"zh"}'
    )
    assert isinstance(message, StartMessage)
    assert message.max_sentence_silence_ms == 1000
    assert message.vocabulary_id is None


def test_start_message_rejects_wrong_sample_rate() -> None:
    with pytest.raises(ValidationError):
        parse_control_message(
            '{"type":"start","sampleRate":48000,"language":"zh"}'
        )


def test_final_event_uses_browser_field_names() -> None:
    event = TranscriptFinal(text="您好", begin_time_ms=0, end_time_ms=420)
    assert json.loads(event.to_json()) == {
        "type": "transcript.final",
        "text": "您好",
        "beginTimeMs": 0,
        "endTimeMs": 420,
    }
```

- [ ] **Step 3: Run the tests and verify import failures**

Run: `python -m pytest tests/test_config.py tests/test_protocol.py -v`

Expected: FAIL because `voice_stt.config` and `voice_stt.protocol` do not exist.

- [ ] **Step 4: Add package and test configuration**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[project]
name = "voice-stt-workbench"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "dashscope>=1.23.1",
  "fastapi>=0.115",
  "pydantic>=2.9",
  "uvicorn[standard]>=0.30",
]

[project.optional-dependencies]
dev = ["httpx>=0.27", "pytest>=8.3", "pytest-asyncio>=0.24"]

[project.scripts]
voice-stt = "voice_stt.__main__:main"

[tool.hatch.build.targets.wheel]
packages = ["src/voice_stt"]

[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"
```

```json
{
  "name": "voice-stt-workbench",
  "private": true,
  "type": "module",
  "scripts": {
    "test:frontend": "node --test tests/frontend/*.test.mjs"
  }
}
```

```dotenv
# .env.example
DASHSCOPE_API_KEY=
DASHSCOPE_WORKSPACE_ID=
```

- [ ] **Step 5: Implement strict environment configuration**

```python
# src/voice_stt/config.py
from dataclasses import dataclass
import os


class ConfigurationError(RuntimeError):
    def __init__(self, missing: tuple[str, ...]) -> None:
        self.missing = missing
        super().__init__("Missing required environment variables: " + ", ".join(missing))


@dataclass(frozen=True)
class Settings:
    api_key: str
    workspace_id: str
    region: str = "cn-beijing"

    @property
    def websocket_url(self) -> str:
        return (
            f"wss://{self.workspace_id}.cn-beijing.maas.aliyuncs.com"
            "/api-ws/v1/inference"
        )

    @classmethod
    def from_env(cls) -> "Settings":
        values = {
            "DASHSCOPE_API_KEY": os.getenv("DASHSCOPE_API_KEY", "").strip(),
            "DASHSCOPE_WORKSPACE_ID": os.getenv("DASHSCOPE_WORKSPACE_ID", "").strip(),
        }
        missing = tuple(name for name, value in values.items() if not value)
        if missing:
            raise ConfigurationError(missing)
        return cls(
            api_key=values["DASHSCOPE_API_KEY"],
            workspace_id=values["DASHSCOPE_WORKSPACE_ID"],
        )
```

- [ ] **Step 6: Implement the control and event models**

Implement Pydantic models with aliases matching the JSON in Step 2. Constrain `sampleRate` to literal `16000`, `language` to `auto | zh | en`, and `maxSentenceSilenceMs` to `200..6000`. Define `parse_control_message` with a discriminated union over `type`. Define server events as frozen Pydantic models whose `to_json()` calls `model_dump_json(by_alias=True, exclude_none=True)`.

The exact stable error codes are:

```python
ErrorCode = Literal[
    "missing_credentials",
    "invalid_configuration",
    "invalid_state",
    "provider_error",
    "client_disconnected",
]
```

- [ ] **Step 7: Run configuration and protocol tests**

Run: `python -m pytest tests/test_config.py tests/test_protocol.py -v`

Expected: all tests pass.

- [ ] **Step 8: Checkpoint**

If Git exists, commit with `feat: define live transcription protocol`; otherwise record that Task 1 passed without a commit.

---

### Task 2: Provider-Neutral Session Contract and Fun-ASR Adapter

**Files:**
- Create: `src/voice_stt/transcriber.py`
- Create: `src/voice_stt/aliyun_fun_asr.py`
- Test: `tests/test_aliyun_fun_asr.py`

**Interfaces:**
- Consumes: `Settings`, `StartMessage`, and all server events from Task 1.
- Produces: `TranscriberSession.start(config)`, `send_audio(frame)`, `stop()`, `abort()`, and `next_event()`.
- Produces: `TranscriberFactory.create() -> TranscriberSession` and `AliyunFunAsrFactory(settings: Settings | None = None)`; omitted settings are loaded lazily when `create()` is called.

- [ ] **Step 1: Define the provider-neutral contract**

```python
# src/voice_stt/transcriber.py
from typing import Protocol

from voice_stt.protocol import ServerEvent, StartMessage


class TranscriberSession(Protocol):
    async def start(self, config: StartMessage) -> None: ...
    async def send_audio(self, frame: bytes) -> None: ...
    async def stop(self) -> None: ...
    async def abort(self) -> None: ...
    async def next_event(self) -> ServerEvent: ...


class TranscriberFactory(Protocol):
    def create(self) -> TranscriberSession: ...
```

- [ ] **Step 2: Write failing mocked-SDK tests**

```python
# tests/test_aliyun_fun_asr.py
import asyncio

import pytest

from voice_stt.aliyun_fun_asr import AliyunFunAsrSession
from voice_stt.config import Settings
from voice_stt.protocol import StartMessage, TranscriptFinal, TranscriptPartial


class FakeRecognition:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.callback = kwargs["callback"]
        self.frames: list[bytes] = []
        self.stopped = False

    def start(self) -> None:
        self.callback.on_open()

    def send_audio_frame(self, frame: bytes) -> None:
        self.frames.append(frame)

    def stop(self) -> None:
        self.stopped = True
        self.callback.on_complete()

    def get_last_request_id(self) -> str:
        return "req-1"

    def get_first_package_delay(self) -> int:
        return 88

    def get_last_package_delay(self) -> int:
        return 37


class FakeResult:
    def __init__(self, sentence: dict[str, object]) -> None:
        self.sentence = sentence

    def get_sentence(self) -> dict[str, object]:
        return self.sentence

    def get_request_id(self) -> str:
        return "req-1"


@pytest.mark.asyncio
async def test_adapter_maps_partial_and_final_events() -> None:
    created: list[FakeRecognition] = []

    def factory(**kwargs: object) -> FakeRecognition:
        recognition = FakeRecognition(**kwargs)
        created.append(recognition)
        return recognition

    session = AliyunFunAsrSession(
        Settings(api_key="key", workspace_id="ws"),
        recognition_factory=factory,
    )
    await session.start(StartMessage(type="start", sampleRate=16000, language="zh"))
    callback = created[0].callback
    callback.on_event(FakeResult({"text": "明天", "begin_time": 0, "end_time": None}))
    callback.on_event(FakeResult({"text": "明天下午三点", "begin_time": 0, "end_time": 820}))

    assert isinstance(await asyncio.wait_for(session.next_event(), 0.1), TranscriptPartial)
    final = await asyncio.wait_for(session.next_event(), 0.1)
    assert isinstance(final, TranscriptFinal)
    assert final.text == "明天下午三点"
```

- [ ] **Step 3: Run the adapter test and verify it fails**

Run: `python -m pytest tests/test_aliyun_fun_asr.py -v`

Expected: FAIL because `AliyunFunAsrSession` does not exist.

- [ ] **Step 4: Implement the callback bridge and session lifecycle**

In `AliyunFunAsrSession.start`, capture `asyncio.get_running_loop()`, create one `asyncio.Queue[ServerEvent]`, and construct the SDK recognition with:

```python
recognition = recognition_factory(
    model="fun-asr-realtime",
    format="pcm",
    sample_rate=16000,
    semantic_punctuation_enabled=False,
    max_sentence_silence=config.max_sentence_silence_ms,
    language_hints=None if config.language == "auto" else [config.language],
    vocabulary_id=config.vocabulary_id,
    callback=callback,
)
```

Before construction, set `dashscope.api_key=settings.api_key` and `dashscope.base_websocket_api_url=settings.websocket_url`. The callback uses `loop.call_soon_threadsafe(queue.put_nowait, event)` for every SDK thread callback. Ignore empty text. Emit `TranscriptFinal` when `sentence["end_time"] is not None`; otherwise emit `TranscriptPartial`. `stop()` runs the blocking SDK call with `asyncio.to_thread`, then emits `SessionMetric` and lets `on_complete` emit `SessionCompleted`. `abort()` is idempotent and never emits patient content.

`AliyunFunAsrFactory` stores optional fixed settings for tests. When settings were omitted, `create()` calls `Settings.from_env()` so the web server can start without credentials and fail safely only when a transcription session is requested.

- [ ] **Step 5: Add lifecycle and error assertions**

Extend `tests/test_aliyun_fun_asr.py` to assert:

```python
await session.send_audio(b"\x00\x01")
assert created[0].frames == [b"\x00\x01"]
await session.stop()
assert created[0].stopped is True
```

Add a fake result with `message="upstream failure"` and `request_id="req-2"`, invoke `callback.on_error(result)`, and assert the next event is `SessionError(code="provider_error", request_id="req-2")`. The event message must not contain the configured API key.

- [ ] **Step 6: Run the adapter tests**

Run: `python -m pytest tests/test_aliyun_fun_asr.py -v`

Expected: all tests pass without network access.

- [ ] **Step 7: Checkpoint**

If Git exists, commit with `feat: add Fun-ASR transcriber adapter`; otherwise record that Task 2 passed without a commit.

---

### Task 3: WebSocket Session State Machine

**Files:**
- Create: `src/voice_stt/session.py`
- Test: `tests/test_session.py`

**Interfaces:**
- Consumes: `parse_control_message`, `ServerEvent`, and `TranscriberFactory`.
- Produces: `run_transcription_session(websocket, factory) -> None`.

- [ ] **Step 1: Write a fake transcriber and failing happy-path test**

```python
# tests/test_session.py
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from voice_stt.protocol import SessionCompleted, SessionStarted, TranscriptFinal
from voice_stt.session import run_transcription_session


class FakeSession:
    def __init__(self) -> None:
        self.frames: list[bytes] = []
        self.events = iter([
            SessionStarted(model="fun-asr-realtime", region="cn-beijing"),
            TranscriptFinal(text="测试成功", begin_time_ms=0, end_time_ms=500),
            SessionCompleted(),
        ])

    async def start(self, config): self.config = config
    async def send_audio(self, frame: bytes): self.frames.append(frame)
    async def stop(self): return None
    async def abort(self): return None
    async def next_event(self): return next(self.events)


class FakeFactory:
    def __init__(self) -> None: self.session = FakeSession()
    def create(self): return self.session


def test_websocket_orders_start_audio_and_stop() -> None:
    app = FastAPI()
    factory = FakeFactory()

    @app.websocket("/ws/transcribe")
    async def endpoint(websocket: WebSocket) -> None:
        await run_transcription_session(websocket, factory)

    with TestClient(app).websocket_connect("/ws/transcribe") as ws:
        ws.send_text('{"type":"start","sampleRate":16000,"language":"zh"}')
        assert ws.receive_json()["type"] == "session.started"
        ws.send_bytes(b"\x00\x00")
        assert ws.receive_json()["type"] == "transcript.final"
        ws.send_text('{"type":"stop"}')
        assert ws.receive_json()["type"] == "session.completed"
    assert factory.session.frames == [b"\x00\x00"]
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python -m pytest tests/test_session.py -v`

Expected: FAIL because `voice_stt.session` does not exist.

- [ ] **Step 3: Implement the explicit session state machine**

Use states `idle`, `recording`, `stopping`, and `closed`. Accept the WebSocket, require `start` as the first frame, create one transcriber, and start a provider-event sender task. If `factory.create()` raises `ConfigurationError`, send `SessionError(code="missing_credentials", message="请配置北京地域的 DASHSCOPE_API_KEY 和 DASHSCOPE_WORKSPACE_ID。")` and close with code `1008`. Binary frames are accepted only in `recording`. A `stop` control moves to `stopping`, awaits `transcriber.stop()`, then waits for `session.completed`. On `WebSocketDisconnect`, call `abort()` and cancel the sender. On invalid message order, send `SessionError(code="invalid_state", message="...")`, abort, and close with code `1008`.

The sender loop is:

```python
async def forward_events(websocket: WebSocket, transcriber: TranscriberSession) -> None:
    while True:
        event = await transcriber.next_event()
        await websocket.send_text(event.to_json())
        if event.type in {"session.completed", "session.error"}:
            return
```

- [ ] **Step 4: Add invalid-order and disconnect tests**

Add tests that send binary data before `start`, send a second `start`, and disconnect while recording. Assert the first two return `invalid_state`; assert disconnect calls fake `abort()` exactly once.

- [ ] **Step 5: Run WebSocket session tests**

Run: `python -m pytest tests/test_session.py -v`

Expected: all tests pass and no async task warnings are emitted.

- [ ] **Step 6: Checkpoint**

If Git exists, commit with `feat: orchestrate browser transcription sessions`; otherwise record that Task 3 passed without a commit.

---

### Task 4: FastAPI Application and Static Workbench Shell

**Files:**
- Create: `src/voice_stt/app.py`
- Create: `src/voice_stt/__main__.py`
- Create: `src/voice_stt/static/index.html`
- Create: `src/voice_stt/static/styles.css`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `Settings`, `AliyunFunAsrFactory`, and `run_transcription_session`.
- Produces: `create_app(factory: TranscriberFactory | None = None) -> FastAPI` and `main() -> None`.

- [ ] **Step 1: Write failing application smoke tests**

```python
# tests/test_app.py
from fastapi.testclient import TestClient

from voice_stt.app import create_app


def test_health_does_not_expose_credentials() -> None:
    response = TestClient(create_app(factory=object())).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "model": "fun-asr-realtime",
        "region": "cn-beijing",
    }


def test_workbench_is_served() -> None:
    response = TestClient(create_app(factory=object())).get("/")
    assert response.status_code == 200
    assert "实时语音转写实验台" in response.text
    assert "DASHSCOPE_API_KEY" not in response.text
```

- [ ] **Step 2: Run the smoke tests and verify they fail**

Run: `python -m pytest tests/test_app.py -v`

Expected: FAIL because `voice_stt.app` does not exist.

- [ ] **Step 3: Build the application factory**

`create_app(factory=None)` must not read credentials during application construction. If `factory` is provided, use it directly; otherwise construct `AliyunFunAsrFactory()` with lazy environment loading. The `/api/health` route returns only the fixed model and region. Mount the static directory and register `/ws/transcribe` before the catch-all index route. `__main__.py` runs `uvicorn.run("voice_stt.app:create_app", factory=True, host="127.0.0.1", port=8000, reload=False)`.

- [ ] **Step 4: Add accessible workbench markup**

The HTML must include:

```html
<main class="workbench">
  <header class="topbar">
    <div><p class="eyebrow">Alibaba Cloud · cn-beijing</p><h1>实时语音转写实验台</h1></div>
    <div id="statusBadge" role="status" aria-live="polite">未连接</div>
  </header>
  <section class="recorder" aria-labelledby="recorderTitle">
    <h2 id="recorderTitle">语音输入</h2>
    <canvas id="levelMeter" width="520" height="96" aria-label="麦克风输入电平"></canvas>
    <button id="recordButton" type="button" aria-pressed="false">开始录音</button>
    <p id="recordingHint">点击后允许浏览器使用麦克风</p>
  </section>
  <section class="transcript" aria-labelledby="transcriptTitle">
    <div class="section-heading"><h2 id="transcriptTitle">实时转写</h2><span id="firstPacketDelay">首包 —</span></div>
    <ol id="finalTranscript" aria-live="polite"></ol>
    <p id="partialTranscript" aria-live="polite"></p>
    <div id="emptyState">开始说话后，识别结果会显示在这里。</div>
    <div class="actions"><button id="copyButton">复制全文</button><button id="downloadButton">下载 TXT</button><button id="clearButton">清空</button></div>
  </section>
</main>
```

Add labelled controls for language (`auto`, `zh`, `en`), silence threshold (`200..6000`, default `1000`), and optional vocabulary ID inside a `<details>` element.

- [ ] **Step 5: Implement responsive styling**

Use CSS custom properties, visible focus rings, minimum 44 px controls, a two-column layout above 900 px, and a single column below 900 px. State classes are `is-idle`, `is-connecting`, `is-recording`, `is-stopping`, `is-completed`, and `is-error`. The recording button must communicate state with icon, text, motion, and color; respect `prefers-reduced-motion`.

- [ ] **Step 6: Run smoke tests**

Run: `python -m pytest tests/test_app.py -v`

Expected: all tests pass.

- [ ] **Step 7: Checkpoint**

If Git exists, commit with `feat: serve transcription workbench`; otherwise record that Task 4 passed without a commit.

---

### Task 5: Transcript State, PCM Worklet, and Browser Controller

**Files:**
- Create: `src/voice_stt/static/transcript-state.js`
- Create: `src/voice_stt/static/pcm-worklet.js`
- Create: `src/voice_stt/static/app.js`
- Test: `tests/frontend/transcript-state.test.mjs`
- Test: `tests/frontend/pcm-worklet.test.mjs`

**Interfaces:**
- Consumes: the WebSocket protocol from Task 1 and DOM IDs from Task 4.
- Produces: `initialTranscriptState()`, `reduceTranscript(state, event)`, `downsampleMono(input, inputRate, outputRate)`, and the complete browser recording lifecycle.

- [ ] **Step 1: Write failing reducer tests**

```javascript
// tests/frontend/transcript-state.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { initialTranscriptState, reduceTranscript } from "../../src/voice_stt/static/transcript-state.js";

test("partial replaces and final appends once", () => {
  let state = initialTranscriptState();
  state = reduceTranscript(state, { type: "transcript.partial", text: "明天" });
  state = reduceTranscript(state, { type: "transcript.partial", text: "明天下午" });
  assert.equal(state.partial, "明天下午");
  state = reduceTranscript(state, {
    type: "transcript.final", text: "明天下午三点", beginTimeMs: 0, endTimeMs: 800,
  });
  assert.equal(state.partial, "");
  assert.deepEqual(state.final, [
    { text: "明天下午三点", beginTimeMs: 0, endTimeMs: 800 },
  ]);
});

test("duplicate final event is ignored", () => {
  const event = { type: "transcript.final", text: "您好", beginTimeMs: 0, endTimeMs: 300 };
  let state = reduceTranscript(initialTranscriptState(), event);
  state = reduceTranscript(state, event);
  assert.equal(state.final.length, 1);
});
```

- [ ] **Step 2: Write failing PCM helper tests**

```javascript
// tests/frontend/pcm-worklet.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { downsampleMono, floatToPcm16 } from "../../src/voice_stt/static/pcm-worklet.js";

test("48 kHz input becomes 16 kHz mono", () => {
  const input = Float32Array.from({ length: 4800 }, (_, index) => Math.sin(index / 20));
  assert.equal(downsampleMono(input, 48000, 16000).length, 1600);
});

test("float samples are clamped into PCM16", () => {
  assert.deepEqual(
    Array.from(floatToPcm16(Float32Array.of(-2, 0, 2))),
    [-32768, 0, 32767],
  );
});
```

- [ ] **Step 3: Run frontend tests and verify export failures**

Run: `npm run test:frontend`

Expected: FAIL because the frontend modules do not exist.

- [ ] **Step 4: Implement the pure transcript reducer**

The reducer returns new objects and never mutates input state. A final event identity is `${beginTimeMs}:${endTimeMs}:${text}`. Store an internal `seenFinalIds` array, clear `partial` on final, update metrics on `session.metric`, and preserve final sentences on `session.completed`. The clear UI action replaces state with `initialTranscriptState()`.

- [ ] **Step 5: Implement deterministic downsampling and chunking**

Export `downsampleMono` and `floatToPcm16` for Node tests. Register `PcmCaptureProcessor` only when `globalThis.AudioWorkletProcessor` exists. Accumulate resampled samples until 1,600 samples are available, then post an `Int16Array` buffer and peak level. Do not send partial chunks during recording; on stop, flush a padded final 1,600-sample chunk only when at least one real sample remains.

- [ ] **Step 6: Run frontend unit tests**

Run: `npm run test:frontend`

Expected: all reducer and PCM tests pass.

- [ ] **Step 7: Implement browser recording and WebSocket lifecycle**

`app.js` must:

1. Open `ws://` or `wss://` based on `location.protocol`.
2. Send the JSON `start` message and wait for `session.started` before starting `getUserMedia`.
3. Create an `AudioContext`, load `/static/pcm-worklet.js`, connect a `MediaStreamAudioSourceNode` to the worklet, and keep output muted.
4. Send each worklet `ArrayBuffer` only while WebSocket state is `OPEN` and UI state is `recording`.
5. Draw the posted peak level in `requestAnimationFrame` and stop the loop on completion/error.
6. On stop, disconnect nodes, stop every media track, send `{"type":"stop"}`, and wait for `session.completed` before resetting controls.
7. Map stable error codes to Chinese messages without exposing raw upstream payloads.
8. Copy and download only joined final text; disable both actions when no final text exists.
9. Always release media tracks and audio context in a single idempotent `cleanupAudio()` function.

- [ ] **Step 8: Add browser-controller safety checks**

Ensure `recordButton` cannot start a second session while connecting/recording/stopping. Treat microphone `NotAllowedError` as “麦克风权限被拒绝，请在浏览器设置中允许访问。” Treat other `getUserMedia` failures as “无法使用麦克风，请检查设备连接。” Close the WebSocket when microphone setup fails after `session.started`.

- [ ] **Step 9: Re-run frontend and Python tests**

Run: `npm run test:frontend`

Expected: all frontend tests pass.

Run: `python -m pytest -v`

Expected: all Python tests pass.

- [ ] **Step 10: Checkpoint**

If Git exists, commit with `feat: stream microphone audio into live transcript`; otherwise record that Task 5 passed without a commit.

---

### Task 6: Documentation, Local Verification, and Failure Modes

**Files:**
- Create: `README.md`
- Modify: `.env.example`
- Test: all existing tests plus local browser verification.

**Interfaces:**
- Consumes: the complete application from Tasks 1–5.
- Produces: reproducible setup and verification commands for future developers.

- [ ] **Step 1: Write the README setup contract**

Document these exact commands:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
$env:DASHSCOPE_API_KEY="replace-with-beijing-key"
$env:DASHSCOPE_WORKSPACE_ID="replace-with-beijing-workspace-id"
.\.venv\Scripts\python.exe -m voice_stt
```

State that the application is available at `http://127.0.0.1:8000`, localhost is permitted to request microphone access, and deployed environments require HTTPS/WSS. Include the privacy behavior, Beijing credential requirement, supported audio path, test commands, and common errors from the design specification.

- [ ] **Step 2: Run all automated checks**

Run: `python -m pytest -v`

Expected: all Python tests pass.

Run: `npm run test:frontend`

Expected: all Node tests pass.

- [ ] **Step 3: Start the app without credentials and verify safe failure**

Run: `python -m voice_stt`

Expected: the UI and `/api/health` load; starting a transcription returns `missing_credentials`, and neither the process output nor browser console contains a credential value.

- [ ] **Step 4: Verify the static UI in a real browser**

Open `http://127.0.0.1:8000` with the in-app Browser. Check desktop and narrow layouts, keyboard focus order, record-button state transitions, empty state, settings labels, and error recovery. Inspect console errors after each flow; expected result is no unexpected errors.

- [ ] **Step 5: Run one credentialed fictional-audio smoke test**

With Beijing credentials configured, say: “您好，我想预约明天下午三点洗牙。” Expected behavior: a partial sentence appears while speaking; one final sentence replaces it after silence; stop reaches `session.completed`; request ID and latency metrics appear; no API Key or raw audio appears in logs.

- [ ] **Step 6: Verify cleanup and privacy**

Stop recording, refresh, and confirm the microphone indicator turns off, transcript is empty, no audio file exists under the workspace, and application logs contain only state, latency, error category, and request ID.

- [ ] **Step 7: Final checkpoint**

If Git exists, commit with `docs: document Fun-ASR workbench setup`; otherwise report all verified commands and explicitly state that no commit was created because the workspace is not a Git repository.

---

## Self-Review Result

- Spec coverage: Tasks 1–6 cover the Beijing endpoint, environment-only credentials, provider adapter boundary, 100 ms PCM16 audio, partial/final replacement semantics, responsive UI, settings, metrics, stable errors, privacy, automated tests, and real-browser verification.
- Placeholder scan: no `TBD`, `TODO`, “implement later,” undefined helper, or deferred error behavior remains.
- Type consistency: `StartMessage`, `ServerEvent`, `TranscriberSession`, `TranscriberFactory`, and `run_transcription_session` are introduced before consumption; browser JSON aliases match the protocol tests and UI controller.
- Scope: authentication, persistence, SIP, LLM, TTS, production deployment, and multi-tenant behavior remain excluded.
