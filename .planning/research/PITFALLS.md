# Domain Pitfalls: AI Video Production / YouTube Publishing

**Domain:** AI Content Creation Pipeline
**Researched:** 2026-07-10
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: YouTube API Quota Exhaustion (Hard Ceiling)

**What goes wrong:** The pipeline uploads 7 videos in a day, hits `403 quotaExceeded`, and ALL YouTube API operations (including analytics reads) stop for 24 hours.

**Why it happens:** Videos.insert costs 1,600 quota units each. Default allocation is 10,000 units/day. Six uploads = 9,600 units. One analytics fetch for 50 videos = 50 units. Total = 9,650 units. The 7th video at 11,200 units exceeds the limit.

**Consequences:**
- Scheduled uploads silently fail
- Analytics collection grinds to a halt
- The brain feedback loop stops (can't get performance data)
- The error is a 403 with reason `quotaExceeded` — must be caught and handled differently from auth failures
- There is NO paid tier — you cannot buy more quota

**Prevention:**
- Implement a `QuotaBudget` tracker that checks `can_spend()` before every operation
- Defer uploads when budget is low (schedule for next Pacific midnight)
- Set Cloud Monitoring alerts at 60% and 85% quota usage
- Submit a quota extension request EARLY (takes 2-4 weeks for audit)
- NEVER use `search.list` — always use `playlistItems.list` (1 vs 100 units)
- Cache aggressively — use ETags for conditional requests at zero quota cost

**Detection:** Track `quota_used` per day in a persistent file. Compare against `DAILY_LIMIT - SAFETY_MARGIN` before each operation. Log warnings at 50%, 75%, 90% thresholds.

### Pitfall 2: OAuth Token Expiration Mid-Upload

**What goes wrong:** The access token (1-hour lifetime) expires during a large video upload. The upload fails with 401 Unauthorized. The resumable upload session URI has a finite lifetime and may also expire.

**Why it happens:** Google OAuth 2.0 access tokens have a 1-hour TTL. The refresh token is long-lived but only works if `access_type=offline` was set during the initial authorization. If the code only refreshes tokens before upload starts, but the upload takes >1 hour, the token expires mid-stream.

**Consequences:**
- Upload fails after spending 1,600 quota units
- The video file was partially transmitted but not processed
- User sees an error but doesn't know why
- The resumable session URI may also expire (404 Not Found), requiring a fresh upload start

**Prevention:**
- Set `access_type=offline` during OAuth setup (this is the draft flow requirement)
- Implement token refresh mid-upload if the client library supports it
- For long uploads, use the google-api-python-client which handles token refresh automatically
- Store the refresh token securely alongside the access token
- Monitor token expiry and refresh proactively before uploads

### Pitfall 3: No Checkpoint Resilience — Full Pipeline Restart on Failure

**What goes wrong:** The pipeline crashes during the render phase (90% done — 5 minutes into rendering). The orchestrator restarts from Stage 1, re-running LLM calls ($$$), re-scraping assets (API limits), and re-rendering (compute time).

**Why it happens:** The current architecture has no checkpoint infrastructure. Every stage produces state in memory or temp directories, but there's no persisted artifact that allows resumption from the last completed stage.

**Consequences:**
- Wasted API costs (LLM calls re-invoked)
- Wasted compute (FFmpeg re-renders)
- Wasted time (8-10 minutes of re-do for a mid-render crash)
- Rate limit exhaustion from re-scraping assets

**Prevention:**
- Every pipeline stage writes a typed, schema-validated JSON artifact to `checkpoints/{run_id}/`
- The orchestrator checks if a checkpoint exists before running a stage:
  - If `checkpoints/script.json` exists and is valid → skip ScriptStage
  - If not → run ScriptStage
- Artifacts are immutable — never overwrite, always write new
- Implement `PipelineState` enum: NOT_STARTED, IN_PROGRESS, COMPLETED, FAILED

## Moderate Pitfalls

### Pitfall 4: Hardcoded API Provider Without Fallback

**What goes wrong:** Google Cloud TTS API key is rotated, service goes down, or quota is exhausted. TTS generation breaks completely. The entire production pipeline stops.

**Why it happens:** The current `tts_generation.py` has a hardcoded proxy URL and API key. No fallback chain. No graceful degradation.

**Prevention:** Implement multi-provider selector with fallback:
- Primary: Google Cloud TTS (highest quality, API cost)
- Fallback: Edge TTS (free, neural, no API key)
- Last resort: pyttsx3 (offline, low quality)
Each provider's availability is checked at runtime, not hardcoded.

### Pitfall 5: Analytics Collection Timing — Collecting Too Early

**What goes wrong:** Analytics are collected immediately after publish. Early data is noisy, misleading, and changes significantly — a video might have 5 views in the first hour and 5,000 in the next.

**Consequences:**
- Brain updater makes decisions on statistically insignificant data
- Pillars and weights get adjusted based on noise
- Content strategy degrades instead of improving

**Prevention:**
- Enforce minimum 24-hour delay before analytics collection
- Use a scheduler: `collect_at = publish_at + timedelta(hours=24)`
- Batch collections don't poll (avoid burning quota on constant checks)
- Implement minimum sample size: don't update brain weights until 3+ videos per pillar

### Pitfall 6: No Schema Validation Enforcement at Stage Boundaries

**What goes wrong:** A broken script artifact (missing scenes, malformed JSON) flows from ScriptStage to AudioStage. AudioStage generates audio for a different number of scenes than VisualStage expects. The compositor crashes because scene counts don't match.

**Why it happens:** The current codebase has JSON Schema files in `schemas/` but they are never programmatically enforced — only used as references. Artifacts are plain Python dicts with no validation at deserialization boundaries.

**Prevention:**
- Validate every artifact against its JSON Schema when read from checkpoints
- Fail fast: if `script.json` doesn't validate against `schemas/script.schema.json`, don't proceed
- Use `jsonschema` library for enforcement
- Validation errors should produce clear messages: "Scene 4 missing 'duration' field (schema: script.schema.json#/properties/scenes/items)"

### Pitfall 7: Multi-Channel OAuth Token Confusion

**What goes wrong:** User authenticates Channel A, then Channel B. The OAuth token for Channel A is overwritten by Channel B's token. Upload attempts fail with authentication errors.

**Why it happens:** All OAuth tokens are stored at `~/.creatorforge/yt-token.json` — a single file. No per-channel isolation.

**Prevention:**
- Name token files per channel: `~/.creatorforge/{channel_name}/yt-token.json`
- Store client ID/secret per channel (they can be the same Google Cloud project, but tokens are channel-specific)
- Validate the channel ID stored in the token matches the channel being used

## Minor Pitfalls

### Pitfall 8: Scheduling Without Privacy Status Awareness

**What goes wrong:** User sets `publishAt` without setting `privacyStatus` to `private`. The API rejects the request with `invalidPublishAt`.

**Why it happens:** The `publishAt` field is only valid when `privacyStatus=private`. YouTube automatically makes it public at the scheduled time. This is non-obvious from the API docs.

**Prevention:**
- Always set `privacyStatus="private"` when `publishAt` is provided
- Validate this combination in the metadata builder
- Document this behavior clearly in the scheduling module

### Pitfall 9: Resumable Session URI Expiry

**What goes wrong:** A video upload is initiated (Step 1), the session URI is obtained, but the actual upload doesn't start for 30+ minutes. The session URI has expired (404 Not Found), and the entire upload initiation must be repeated.

**Prevention:**
- Upload the video file immediately after obtaining the session URI (don't queue the URI)
- If a delay is unavoidable, re-initiate the upload (the earlier quota cost has already been spent)
- Implement retry logic: if 404 on upload, restart from initiation step

### Pitfall 10: Category ID as String Instead of Number

**What goes wrong:** `categoryId` is set to "Education" instead of "27". The API rejects the request with `invalidCategoryId`.

**Prevention:**
- Always use numeric category IDs (look up via `videoCategories.list`)
- Cache category ID mappings locally
- Validate categoryId is numeric before sending

### Pitfall 11: `selfDeclaredMadeForKids` Not Set

**What goes wrong:** The upload request omits `selfDeclaredMadeForKids`. The API may reject the request or default to the channel-level setting, which could be wrong.

**Prevention:**
- Always include `status.selfDeclaredMadeForKids` in every upload
- Default to `false` for most content creator use cases
- Make it configurable per-channel in `channel_config.json`

### Pitfall 12: MoviePy Frame Pull on Large Videos

**What goes wrong:** A 5-minute video takes 10+ minutes to render because MoviePy decodes every frame into Python (numpy) for even trivial operations like concatenation.

**Prevention:**
- Use FFmpeg filter graphs directly — single invocation, no frame data in Python memory
- Use a declarative timeline abstraction (like `video-arrange`'s approach)
- Reserve MoviePy for operations that genuinely need frame-level access (effects, analysis)

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| OAuth token management | Token expiry mid-upload | google-api-python-client handles auto-refresh; test with >1hr upload |
| YouTube upload | Quota exhaustion before audit | Submit audit request week 1; implement QuotaBudget with scheduling |
| Analytics collection | Fetching data too early | Enforce 24h minimum delay; schedule collection, don't poll |
| Force alignment | No reliable local alignment | Evaluate WhisperX, Deepgram API, or char-based timing as fallback |
| Brain updater | Overfitting to single-video noise | Require minimum 3 videos per pillar before weight adjustment |
| Multi-channel | Token overwrite between channels | Per-channel token files with channel ID validation |
| Render pipeline | MoviePy bottleneck for concatenation | Single FFmpeg filter_complex instead of per-scene rendering |
| Quality gates | Gate proliferation without validation | Dry-pass mode for 2 weeks before enforcement graduation |

## Sources

- Official YouTube Data API v3 documentation — https://developers.google.com/youtube/v3 (HIGH)
- YouTube Quota Calculator — https://developers.google.com/youtube/v3/determine_quota_cost (HIGH)
- Resumable Upload Protocol — https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol (HIGH)
- YouTube Quota Exceeded Guide 2026 — https://outlierkit.com/resources/youtube-api-quota/ (MEDIUM, verified against official)
- YouTube Quota Squeezing Lessons — https://dev.to/qcrao/what-i-learned-squeezing-the-youtube-data-api-v3-quota-for-a-side-project (HIGH, real-world verification)
- Self-Improving Content Engine — https://www.leanboat.io/blog/self-improving-content-engine (HIGH)
- 4-Plane Architecture — https://generativeai.pub/the-4-plane-architecture-of-ai-native-content-engineering (HIGH)
- Showrunner ADRs — https://github.com/divi-vijayakumar/Showrunner (MEDIUM)
