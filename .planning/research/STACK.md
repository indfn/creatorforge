# Technology Stack Research

**Project:** CreatorForge — AI Content Creation / YouTube Publishing Pipeline
**Researched:** 2026-07-10
**Confidence:** HIGH

## Recommended Stack

The current Python/Flask stack is appropriate for this domain. No framework changes needed. Primary recommendations are about *how* to use existing tools and *which libraries* to fill gaps.

### Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.10+ | Primary language | Existing codebase; all AI/ML libraries support it |
| Flask | 2.x | Recon UI (web interface) | Already used; no benefit in migrating to FastAPI for current scope |
| google-api-python-client | latest | YouTube Data API v3 + Analytics API | Official Google client — handles OAuth, token refresh, resumable uploads |
| google-auth-oauthlib | latest | OAuth 2.0 flow management | Standard for desktop/CLI OAuth with Google |

### Media Processing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FFmpeg | 6.x+ | Video/audio composition | Industry standard. Single invocation per render via filter_complex. No frame data in Python. |
| Pydub | latest | Audio manipulation | Lightweight audio operations (volume, concat, format conversion) |
| Pillow | 10.x+ | Image compositing for slides/frames | Already required; used for Ken Burns effect, text overlays on static images |
| WhisperX | latest | Force alignment for captions | Word-level timestamps for caption sync. Evaluate reliability — may need cloud fallback (Deepgram) |

### AI / ML

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| OpenAI Whisper API | n/a | Video transcription for research | Already integrated; highest accuracy |
| Gemini 3.1 Flash TTS | n/a | Voiceover generation | Already integrated; good quality/free tier |
| Multi-provider LLM (OpenAI-compatible) | n/a | Script/hook/metadata generation | Already have Ollama + OpenAI support |
| Pexels API | n/a | Stock video/image sourcing | Free tier usable; Pixabay as fallback |
| MusicGen (facebook/musicgen-small) | n/a | Background music generation | Local GPU model; cache by mood |

### Support Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| jsonschema | latest | Artifact validation at stage boundaries | Validate every checkpoint before consumption |
| atomicwrites | latest | Safe file writes for tracker state | Prevent partial writes to brain.json and tracker-state.json |
| portalocker | latest | File locking for concurrent access | Multi-process access to state files |
| schedule | latest | Python job scheduler | Analytics collection scheduling, upload deferral |
| redis + celery | optional | Async job queue for parallel renders | Only needed at 10+ channels scale |
| pygame | latest | Audio analysis utilities | Duration detection, sample rate conversion |

### Infrastructure

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| SQLite | 3.x | Asset cache, job state | Already used; sufficient for single-channel deployment |
| PostgreSQL | 16.x | Production analytics store | Only needed at 10+ channels scale or multi-process deployment |
| File system | n/a | Checkpoint artifacts, asset cache | Simple, fast, no new dependencies |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Web framework | Flask | FastAPI | FastAPI has better async support, but current codebase is Flask with minimal request load. Migration not worth the churn. |
| Video processing | FFmpeg (subprocess) | MoviePy | MoviePy pulls every frame into numpy — 10x slower for concatenation/composition. FFmpeg filter_complex is faster and memory-efficient. |
| Job queue | None (direct execution) | Celery + Redis | Not needed at single-channel scale. Add at 10+ channels. |
| OAuth library | google-auth-oauthlib | Custom HTTP | Google's official library handles token refresh and resumable uploads automatically. Don't reimplement. |
| Analytics DB | JSON files | PostgreSQL | Current scale doesn't need Postgres. JSON files are sufficient for <10 channels. |
| Force alignment | WhisperX | Deepgram API | Deepgram is paid-per-minute. Start with WhisperX (local), add Deepgram as fallback if unreliable. |
| BGM generation | MusicGen (local) | Suno API | Suno is paid. MusicGen is free, runs locally, and is good enough for background tracks. |

## Installation

```bash
# Core — already in requirements.txt
pip install google-api-python-client google-auth-oauthlib

# Media processing
pip install ffmpeg-python pydub Pillow

# Validation and state safety
pip install jsonschema atomicwrites portalocker

# Optional: audio analysis
pip install librosa

# Optional: force alignment
pip install whisperx

# Optional: background music
pip install soundfile
```

## Sources

- YouTube Data API v3 client library: google-api-python-client (HIGH: official Google library)
- Resumable upload protocol: FFmpeg subprocess for video composition (HIGH: industry standard)
- OAuth flow: google-auth-oauthlib (HIGH: official Google library)
- Force alignment: WhisperX (MEDIUM: open-source, need to verify reliability at scale)
- Background music: MusicGen (MEDIUM: local GPU required, good quality for background)
