# Minimal STT → LLM → TTS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a standalone local web app that records one Chinese utterance, transcribes it, generates a concise answer, and plays the synthesized answer.

**Architecture:** A single FastAPI process serves one static page and one multipart endpoint. The endpoint sequentially calls Alibaba Cloud Model Studio `qwen3-asr-flash`, `qwen3.7-flash`, and `qwen3-tts-flash`, then returns the transcript, reply, temporary audio URL, and stage timings.

**Tech Stack:** Python 3.10+, FastAPI, Uvicorn, OpenAI Python SDK, HTTPX, python-dotenv, browser MediaRecorder, plain HTML/CSS/JavaScript.

## Global Constraints

- Create a new project at `E:\YinoVapi\Voice-STT-LLM-TTS-HelloWorld`; do not modify either existing voice project.
- Keep the implementation single-turn and non-streaming.
- Do not add login, database, conversation history, real-time captions, interruption, deployment configuration, or provider abstractions.
- Do not add automated tests, as explicitly requested by the user; use the exact manual checks in Task 3.
- Use UTF-8 for all source files and Chinese UI/error text.
- Never place the real API key in source, frontend assets, responses, logs, `.env.example`, or commits.
- Accept only `audio/webm`, `audio/ogg`, `audio/wav`, and `audio/mpeg`, with a 10 MB server-side limit.
- Limit browser recordings to 60 seconds.
- Default models are `qwen3-asr-flash`, `qwen3.7-flash`, and `qwen3-tts-flash`; default TTS voice is `Cherry`.

---

## File Map

- `Voice-STT-LLM-TTS-HelloWorld/.env.example`: safe configuration names and non-secret defaults.
- `Voice-STT-LLM-TTS-HelloWorld/.gitignore`: exclude `.env`, `.venv`, Python caches, and local logs.
- `Voice-STT-LLM-TTS-HelloWorld/requirements.txt`: minimal runtime dependencies.
- `Voice-STT-LLM-TTS-HelloWorld/README.md`: shortest Windows setup, run, and usage instructions.
- `Voice-STT-LLM-TTS-HelloWorld/app/__init__.py`: package marker.
- `Voice-STT-LLM-TTS-HelloWorld/app/config.py`: environment loading and validation.
- `Voice-STT-LLM-TTS-HelloWorld/app/bailian.py`: sequential STT, LLM, and TTS API calls.
- `Voice-STT-LLM-TTS-HelloWorld/app/main.py`: FastAPI routes, upload validation, and response construction.
- `Voice-STT-LLM-TTS-HelloWorld/app/static/index.html`: single-screen Chinese UI.
- `Voice-STT-LLM-TTS-HelloWorld/app/static/app.js`: recording, upload, rendering, and playback.
- `Voice-STT-LLM-TTS-HelloWorld/app/static/styles.css`: compact responsive styling.

---

### Task 1: Minimal Backend Pipeline

**Files:**
- Create: `Voice-STT-LLM-TTS-HelloWorld/.env.example`
- Create: `Voice-STT-LLM-TTS-HelloWorld/.gitignore`
- Create: `Voice-STT-LLM-TTS-HelloWorld/requirements.txt`
- Create: `Voice-STT-LLM-TTS-HelloWorld/app/__init__.py`
- Create: `Voice-STT-LLM-TTS-HelloWorld/app/config.py`
- Create: `Voice-STT-LLM-TTS-HelloWorld/app/bailian.py`
- Create: `Voice-STT-LLM-TTS-HelloWorld/app/main.py`

**Interfaces:**
- Consumes: multipart field `audio`; environment variables listed below.
- Produces: `GET /health`, `GET /`, and `POST /api/voice-chat`.
- Produces: `run_voice_chat(audio_bytes: bytes, mime_type: str, settings: Settings) -> VoiceResult`.

- [ ] **Step 1: Create safe project configuration**

Create `.env.example`:

```env
DASHSCOPE_API_KEY=
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_TTS_URL=https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
STT_MODEL=qwen3-asr-flash
LLM_MODEL=qwen3.7-flash
TTS_MODEL=qwen3-tts-flash
TTS_VOICE=Cherry
```

Create `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
*.py[cod]
*.log
```

Create `requirements.txt`:

```text
fastapi>=0.115
uvicorn[standard]>=0.32
openai>=1.55
httpx>=0.27
python-multipart>=0.0.12
python-dotenv>=1.0
```

- [ ] **Step 2: Implement immutable environment settings**

Create `app/config.py` with a frozen `Settings` dataclass containing:

```python
api_key: str
base_url: str
tts_url: str
stt_model: str
llm_model: str
tts_model: str
tts_voice: str
max_audio_bytes: int = 10 * 1024 * 1024
```

Implement `get_settings() -> Settings` using `load_dotenv()` and environment defaults copied from `.env.example`. Add `Settings.is_configured` that returns `bool(api_key)`.

- [ ] **Step 3: Implement the three model calls**

Create `app/bailian.py` with:

```python
@dataclass(frozen=True)
class VoiceResult:
    transcript: str
    reply: str
    audio_url: str
    timings_ms: dict[str, int]

def run_voice_chat(
    audio_bytes: bytes,
    mime_type: str,
    settings: Settings,
) -> VoiceResult:
    ...
```

Use one `OpenAI(api_key=settings.api_key, base_url=settings.base_url, timeout=60)` client.

For STT, encode the uploaded bytes as a data URL and call:

```python
client.chat.completions.create(
    model=settings.stt_model,
    messages=[{
        "role": "user",
        "content": [{
            "type": "input_audio",
            "input_audio": data_url,
        }],
    }],
    extra_body={
        "asr_options": {
            "language": "zh",
            "enable_itn": True,
        }
    },
)
```

Trim `response.choices[0].message.content`; raise `VoicePipelineError("stt", "没有识别到有效语音")` when empty.

For LLM, call:

```python
client.chat.completions.create(
    model=settings.llm_model,
    messages=[
        {
            "role": "system",
            "content": "你是一个简洁、友好的中文语音助手。直接回答问题，控制在200个汉字以内，不使用Markdown表格。",
        },
        {"role": "user", "content": transcript},
    ],
    extra_body={"enable_thinking": False},
)
```

Trim the reply; raise `VoicePipelineError("llm", "大模型没有返回有效回答")` when empty.

For TTS, use `httpx.Client(timeout=60)` to POST `settings.tts_url` with:

```python
headers = {
    "Authorization": f"Bearer {settings.api_key}",
    "Content-Type": "application/json",
    "X-DashScope-SSE": "disable",
}
payload = {
    "model": settings.tts_model,
    "input": {
        "text": reply,
        "voice": settings.tts_voice,
        "language_type": "Chinese",
    },
}
```

Call `response.raise_for_status()` and extract `response.json()["output"]["audio"]["url"]`; raise `VoicePipelineError("tts", "语音合成没有返回音频")` when absent.

Record integer milliseconds for `stt`, `llm`, `tts`, and `total`. Catch provider/HTTP/parsing exceptions at each stage and rethrow `VoicePipelineError(stage, user_message)` without exposing keys or raw provider payloads.

- [ ] **Step 4: Implement FastAPI routes and validation**

Create `app/main.py`:

- Mount `/static` from `app/static`.
- `GET /` returns `app/static/index.html`.
- `GET /health` returns `{"status": "ok"}`.
- `POST /api/voice-chat` accepts `UploadFile` field `audio`.
- Normalize the content type by removing `;codecs=...`.
- Reject unsupported types, empty files, and files over `settings.max_audio_bytes` with `400`.
- Return `503` when `settings.is_configured` is false.
- Run the blocking provider pipeline with `await asyncio.to_thread(...)`.
- Map `VoicePipelineError` to `502` with `{"detail": "<stage>: <message>"}`.
- Return `VoiceResult` as JSON.

- [ ] **Step 5: Perform backend smoke checks**

Run:

```powershell
python -m compileall app
python -c "from app.config import get_settings; print(get_settings().stt_model, get_settings().llm_model, get_settings().tts_model)"
```

Expected: compilation succeeds and prints:

```text
qwen3-asr-flash qwen3.7-flash qwen3-tts-flash
```

- [ ] **Step 6: Commit the backend**

```powershell
git add -- "Voice-STT-LLM-TTS-HelloWorld"
git commit -m "feat: add minimal voice model pipeline"
```

---

### Task 2: Single-Screen Recording UI

**Files:**
- Create: `Voice-STT-LLM-TTS-HelloWorld/app/static/index.html`
- Create: `Voice-STT-LLM-TTS-HelloWorld/app/static/app.js`
- Create: `Voice-STT-LLM-TTS-HelloWorld/app/static/styles.css`

**Interfaces:**
- Consumes: `POST /api/voice-chat` JSON response from Task 1.
- Produces: browser recording controls, transcript/reply display, timing display, and TTS playback.

- [ ] **Step 1: Create the UTF-8 HTML shell**

Create `index.html` with `lang="zh-CN"` and `<meta charset="UTF-8">`. Include:

- Page title “极简语音问答”.
- Status text with initial value “准备就绪”.
- Buttons `#start-button`, `#stop-button`, and `#reset-button`.
- Recording seconds `#seconds`.
- Output elements `#transcript`, `#reply`, and `#timings`.
- Error element `#error`.
- `<audio id="answer-audio" controls hidden></audio>`.
- Links to `/static/styles.css` and `/static/app.js`.

- [ ] **Step 2: Implement browser recording**

In `app.js`, request:

```javascript
navigator.mediaDevices.getUserMedia({ audio: true })
```

Prefer `audio/webm;codecs=opus`, fall back to `audio/webm`, and show a Chinese error if MediaRecorder is unavailable. Collect chunks, update elapsed seconds once per second, and automatically stop at 60 seconds. Always stop all media tracks after recording, reset, or failure.

- [ ] **Step 3: Upload and render the full answer**

On stop:

```javascript
const form = new FormData();
form.append("audio", blob, "recording.webm");
const response = await fetch("/api/voice-chat", {
  method: "POST",
  body: form,
});
```

Show sequential status text: “正在上传” and then “正在识别、思考并合成语音”. On success:

- Set `#transcript` to `payload.transcript`.
- Set `#reply` to `payload.reply`.
- Render `stt / llm / tts / total` milliseconds in `#timings`.
- Set the audio element `src` to `payload.audio_url`, unhide it, and call `audio.play()`.
- Ignore only an autoplay rejection so manual playback remains available.

On failure, display `payload.detail` or the HTTP status, restore the start button, and leave the microphone released.

- [ ] **Step 4: Add compact responsive styling**

Use one centered card with a maximum width near `760px`, clear button states, two result panels, visible focus states, a readable error panel, and a mobile breakpoint. Do not add a component library, build step, images, animations, or theme switching.

- [ ] **Step 5: Perform static checks**

Run:

```powershell
node --check app\static\app.js
```

Expected: exit code `0` with no syntax output.

Open the HTML file through the running FastAPI service and confirm the Chinese labels render without mojibake.

- [ ] **Step 6: Commit the UI**

```powershell
git add -- "Voice-STT-LLM-TTS-HelloWorld/app/static"
git commit -m "feat: add minimal voice chat interface"
```

---

### Task 3: Setup Documentation and Manual End-to-End Verification

**Files:**
- Create: `Voice-STT-LLM-TTS-HelloWorld/README.md`
- Create locally, never commit: `Voice-STT-LLM-TTS-HelloWorld/.env`

**Interfaces:**
- Consumes: the application from Tasks 1 and 2 and the user-provided Alibaba Cloud API key.
- Produces: a runnable local service at `http://127.0.0.1:8000`.

- [ ] **Step 1: Write the shortest Windows setup guide**

Document these commands:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Document that the user must put the real key only in `.env`, then open:

```text
http://127.0.0.1:8000
```

Describe the three default models and state that recording audio is sent to Alibaba Cloud Model Studio for processing.

- [ ] **Step 2: Create the local `.env` safely**

Copy `.env.example` to `.env` and place the user-provided API key in `DASHSCOPE_API_KEY`. Do not print the key, include it in command output, or stage `.env`.

Verify ignore behavior:

```powershell
git check-ignore -v "Voice-STT-LLM-TTS-HelloWorld/.env"
```

Expected: `.gitignore` identifies `.env` as ignored.

- [ ] **Step 3: Install dependencies and start the service**

Create `.venv`, install `requirements.txt`, and launch Uvicorn as a hidden background process bound to `127.0.0.1:8000`. If port 8000 is already occupied by the earlier prototype, stop only that known process or select port 8001 and report the final URL.

- [ ] **Step 4: Verify local HTTP behavior**

Run:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/
```

Expected:

- Health status is `ok`.
- Home page returns HTTP `200`.
- Returned HTML contains “极简语音问答”.

- [ ] **Step 5: Perform one real voice round trip**

In Chrome or Edge:

1. Open the reported local URL.
2. Allow microphone access.
3. Record “你好，请用一句话介绍你自己。”
4. Stop and wait for completion.
5. Confirm transcript text is present.
6. Confirm the LLM answer text is present and under 200 Chinese characters.
7. Confirm the audio player appears and the answer can be heard.
8. Confirm the page shows STT, LLM, TTS, and total timings.
9. Confirm the browser page, terminal output, and repository files do not expose the API key.

- [ ] **Step 6: Commit documentation and inspect final scope**

```powershell
git add -- "Voice-STT-LLM-TTS-HelloWorld/README.md"
git commit -m "docs: document minimal voice chat setup"
git status --short
```

Expected: `.env`, `.venv`, caches, and logs are absent from Git status. Existing unrelated user changes remain untouched.

