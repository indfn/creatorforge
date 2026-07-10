# Architecture Research

**Domain:** AI Content Creation / Video Publishing Pipeline
**Researched:** 2026-07-10
**Confidence:** HIGH

## Standard Architecture

### System Overview

The modern AI video production ecosystem has converged on a **multi-agent, artifact-driven pipeline architecture**. Producers like Project Montage (Google), Showrunner, CineMate, OpenMontage, and montage-ai all follow the same structural pattern despite different implementation stacks. The canonical shape:

```
┌────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                              │
│  Central agent (brain) manages state, routes between phases,       │
│  enforces quality gates, and writes checkpoints for resumability   │
└────────────┬──────────────┬──────────────┬─────────────────────────┘
             │              │              │
    ┌────────▼───┐  ┌──────▼──────┐  ┌─────▼────────┐
    │ CONTEXT    │  │ SIGNALING   │  │ PRODUCTION   │
    │ PLANE      │  │ & PRIORITY  │  │ PLANE        │
    │ (Research  │  │ PLANE       │  │ (Script →    │
    │  + Brain)  │  │ (Trend →    │  │  Audio →     │
    │            │  │  Score →    │  │  Visual →    │
    │            │  │  Decide)    │  │  Render)     │
    └──────┬─────┘  └──────┬──────┘  └──────┬───────┘
           │               │                 │
           └───────────────┼─────────────────┘
                           │
                    ┌──────▼──────┐
                    │ DISTRIBUTION│
                    │ PLANE       │
                    │ (Upload +   │
                    │  Schedule + │
                    │  Metadata)  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ ANALYTICS   │
                    │ FEEDBACK    │◄── Closes the loop
                    │ PLANE       │    back to Signaling
                    └─────────────┘
```

This differs from the current CreatorForge 5-stage linear pipeline (**Discover → Angle → Script → Post → Analyze**) in a critical way: **modern architectures treat these as parallel planes with continuous feedback, not sequential stages with a single pass.**

The key insight from LASEV (multi-agent educational video), the 4-Plane architecture (Manor 2026), and Showrunner is that production and distribution run as mesh networks of communicating agents, not assembly lines.

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Agent Brain / Orchestrator** | Maintains global state, ICP, content pillars, learning weights; routes between phases | JSON file (agent-brain.json) or DB; read by scoring, written by analytics updater |
| **Context Plane** | Knowledge base — competitor data, topic research, brand guidelines, performance history | Vector DB (pgvector, ChromaDB) + JSONL topic stores + SQLite cache |
| **Signaling & Prioritization** | Decides what to produce and when — scores topics against brain, detects trends, prioritizes queue | LLM-based scoring engine + rule-based filters + priority queue |
| **Script Production** | Generates structured scripts, hooks, angles, scene descriptions | LLM multi-agent (scriptwriter, validator, character designer) with Pydantic validation |
| **Audio Production** | TTS generation, force alignment, music/BGM selection | Multi-provider TTS with fallback chain (Google Cloud → Edge → pyttsx3) + MusicGen |
| **Visual Production** | Asset sourcing (b-roll, images, SFX), scene rendering, animations | Pexels/Pixabay scrapers + FFmpeg compositor + optional Manim/Remotion for animations |
| **Render Engine** | Composes audio + visuals + captions into final video | FFmpeg single-pass filter_compose or multi-runtime (HyperFrames/Remotion/FFmpeg selector) |
| **Distribution** | YouTube upload, OAuth management, scheduling, metadata optimization | Google OAuth 2.0 + resumable upload protocol + per-channel config |
| **Analytics Feedback** | Performance data collection, cross-channel aggregation, brain weight evolution | YouTube Analytics API collector + insight aggregator + brain updater |
| **Quality Gates** | Pre-publish validation, schema checks, human review when needed | Schema validation + automated checks (dry-pass → enforcement graduation) + HITL approval |

## Current vs. Recommended Architecture

### Current Architecture (CreatorForge)

```
Discover ─► Angle ─► Script ─► Post ─► Analyze
   │                                        │
   └──────────────────┬─────────────────────┘
                      ▼
               Agent Brain
            (agent-brain.json)
```

**Problems with the current 5-stage linear pipeline:**
1. **No parallel execution** — Audio and visual production are serialized despite having no data dependency
2. **No checkpoint/state persistence** — If a stage fails mid-way, the entire pipeline restarts
3. **Analytics only feeds back at the end** — The loop is coarse-grained; no real-time adjustment
4. **No quality gates between stages** — Garbage propagates forward; validation is schema-only (not enforced)
5. **Stubs = 70% surface area** — Publishing, analytics, visual production, rendering are all placeholder

### Recommended Architecture (Four-Plane Mesh)

```
┌──────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (Agent Brain)                      │
│  agent-brain.json + channel-specific brain.json                   │
│  Manages: pipeline state, checkpoints, routing, error recovery    │
└──┬───────────────┬───────────────┬────────────────┬───────────────┘
   │               │               │                │
   ▼               ▼               ▼                ▼
┌───────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│SIGNAL │    │PRODUCTION│    │DISTRIBUTE│    │ANALYTICS │
│Plane  │───►│Plane     │───►│Plane     │───►│Plane     │──┐
│       │    │          │    │          │    │          │  │
│Score  │    │Script   │    │OAuth    │    │Collector │  │
│Topics │    │Audio    │    │Upload   │    │Insights  │  │
│Queue  │    │Visual   │    │Schedule │    │Updater   │  │
│       │    │Render   │    │Metadata │    │          │  │
└───────┘    └──────────┘    └──────────┘    └──────────┘  │
                                                           │
                                                           │
                ┌──────────────────────────────────────────┘
                │
                ▼
          ┌──────────┐
          │ CONTEXT  │
          │ PLANE    │
          │          │
          │Embeds    │
          │Cache     │
          │Brain     │
          │History   │
          └──────────┘
```

**Key differences:**
- **Parallel execution**: Audio (TTS) + Visual (asset scraping/image gen) run concurrently after Script completes
- **Checkpointed**: Each stage produces a typed artifact; pipeline can resume from last successful checkpoint
- **Enforced quality gates**: Artifact schema validation at every boundary, not just reference
- **Real-time feedback**: Analytics updates the brain continuously, not batch-at-end
- **Clear separation**: Distribution plane has its own sub-lifecycle (OAuth → Quota check → Upload → Verify)

## Data Flow

### Complete Video Pipeline Flow

```
1. TRIGGER: User runs /viral:produce or scheduled job fires
       │
       ▼
2. SIGNALING PLANE ──────────────────────────────────────────────
   │  ┌──────────────────────────────────────────────────┐
   │  │ scoring/engine.py reads agent-brain.json          │
   │  │ Picks highest-score topic from topics JSONL      │
   │  │ Creates ProductionOrder (schema-validated)       │
   │  │ Writes checkpoint: production_order.json          │
   │  └──────────────────────────────────────────────────┘
       │
       ▼
3. PRODUCTION PLANE ──────────────────────────────────────────────
   │  ┌─────────────────────┐     ┌─────────────────────┐
   │  │ STAGE 1: Script     │     │ STAGE 2: Angle/Hook │
   │  │ LLM generates       │     │ LLM generates       │
   │  │ full script JSON    │     │ hook variants       │
   │  │ ← Checkpoint        │     │ ← Checkpoint        │
   │  └──────────┬──────────┘     └──────────┬──────────┘
   │             │                           │
   │             └──────────┬────────────────┘
   │                        ▼
   │             ┌─────────────────────┐
   │             │ STAGE 3: Template   │
   │             │ Select scene template│
   │             │ based on script mood│
   │             │ ← Checkpoint        │
   │             └──────────┬──────────┘
   │                        │
   │        ┌───────────────┼───────────────┐
   │        ▼               ▼               ▼
   │  ┌──────────┐    ┌──────────┐    ┌──────────┐
   │  │ AUDIO    │    │ VISUAL   │    │ MUSIC    │
   │  │ Track    │    │ Assets   │    │ Track    │
   │  │          │    │          │    │          │
   │  │ TTS gen  │    │ Pexels   │    │ MusicGen │
   │  │ via      │    │ scrape   │    │ generate │
   │  │ Gemini   │    │ or Pixabay│   │ or select│
   │  │ 3.1 Flash│    │          │    │ from lib │
   │  │          │    │          │    │          │
   │  │ Force    │    │ Fallback │    │ Volume   │
   │  │ align    │    │ chart gen│    │ normalize│
   │  │ (word-   │    │ if needed│    │ -18dB    │
   │  │ level    │    │          │    │          │
   │  │ timings) │    │          │    │          │
   │  └────┬─────┘    └─────┬────┘    └─────┬────┘
   │       │                │               │
   │       └────────┬───────┴───────────────┘
   │                ▼
   │     ┌──────────────────────┐
   │     │ STAGE 4: Compose     │
   │     │ FFmpeg timeline:     │
   │     │ scenes + audio +     │
   │     │ captions + BGM       │
   │     │ ← Checkpoint         │
   │     └──────────┬───────────┘
   │                ▼
   │     ┌──────────────────────┐
   │     │ STAGE 5: Render      │
   │     │ FFmpeg single-pass   │
   │     │ Output: final.mp4    │
   │     │ ← Checkpoint         │
   │     └──────────┬───────────┘
   │                │
   ▼                │
4. DISTRIBUTION PLANE ◄──────────┘
   │  ┌──────────────────────────────────────────────┐
   │  │ QUOTA CHECK: Can we spend 1,600 units today? │
   │  │ ┌── NO ──► Schedule for next day ───────┐    │
   │  │ │                                        │    │
   │  │ ▼                                        │    │
   │  │ OAUTH FLOW:                               │    │
   │  │ 1. Load token from ~/.creatorforge/       │    │
   │  │ 2. Refresh if expired (offline access)    │    │
   │  │ 3. Build authenticated youtube client     │    │
   │  │                                           │    │
   │  │ RESUMABLE UPLOAD:                          │    │
   │  │ 1. POST metadata → get session URI        │    │
   │  │ 2. Upload file in chunks (256KB multiples) │    │
   │  │ 3. Exponential backoff on 5xx errors       │    │
   │  │                                           │    │
   │  │ SCHEDULE (optional):                       │    │
   │  │ If publish_at set:                         │    │
   │  │   privacyStatus = private                  │    │
   │  │   publishAt = calculated peak time         │    │
   │  │ ← Checkpoint: publish_log.json             │    │
   │  └────────────────────────────────────────────┘    │
       │
       ▼
5. ANALYTICS PLANE ──────────────────────────────────────────
   │  ┌──────────────────────────────────────────┐
   │  │ COLLECT:                                   │
   │  │ 24h after publish:                        │
   │  │  - views, watchTime, averageViewDuration  │
   │  │  - likes, dislikes, comments, shares       │
   │  │  - trafficSource, deviceType               │
   │  │                                            │
   │  │ AGGREGATE:                                 │
   │  │  - Per-topic performance                   │
   │  │  - Per-pillar distribution                 │
   │  │  - Thumbnail CTR correlation               │
   │  │                                            │
   │  │ UPDATE BRAIN:                              │
   │  │  - Adjust learning weights                  │
   │  │  - Promote/demote pillar keywords           │
   │  │  - Update content gap analysis              │
   │  └──────────────────────────────────────────┘    │
       │
       ▼
6. LOOP CLOSED: Brain updated → next topic scoring
                 accounts for new performance data
```

### State Management

```
State Flow:

agent-brain.json (read) ──► scoring/engine.py ──► topic JSONL
       ▲                                                │
       │                                                ▼
       │                                     bridge.py creates
       │                                     ProductionOrder
       │                                                │
       │                                                ▼
       │                              checkpoints/ dir (JSON state)
       │                                per-stage artifacts:
       │                                - production_order.json
       │                                - script.json
       │                                - audio_timeline.json
       │                                - visual_manifest.json
       │                                - render_spec.json
       │                                - publish_log.json
       │                                                │
       │                                                ▼
       │                              analytics/collector.py
       │                                     │
       │                                     ▼
       └──────────── analytics/brain_updater.py
```

### YouTube OAuth Draft Flow vs. Published Flow

#### Draft / Development Flow (what the current stub needs)

```
User channel owner
    │
    ▼
1. Create Google Cloud Project → Enable YouTube Data API v3
2. Create OAuth 2.0 credentials (Desktop app type for CLI)
3. Configure Consent Screen → Add youtube.upload scope
4. Run setup-yt-oauth.py
   │
   ▼
┌───────────────────────────────────────────────────┐
│ OAuth SETUP SCRIPT                                 │
│                                                     │
│ 1. Open browser to Google consent URL              │
│ 2. User authenticates, grants youtube.upload scope │
│ 3. Google redirects to localhost callback with code │
│ 4. Script exchanges code for access + refresh token│
│ 5. Stores tokens at ~/.creatorforge/yt-token.json   │
│ 6. File permissions set to 0600                    │
│                                                     │
│ Token File Format:                                   │
│ {                                                    │
│   "token": "ya29...",           ← expires ~1 hour   │
│   "refresh_token": "1//...",    ← long-lived        │
│   "client_id": "...",                               │
│   "client_secret": "...",                           │
│   "scopes": ["https://...youtube.upload"],          │
│   "expiry": "2026-07-10T12:00:00Z"                 │
│ }                                                    │
└───────────────────────────────────────────────────┘
```

#### Published / Quota-Extended Flow

```
User channel owner
    │
    ▼
1. Google Cloud Project → API audit required
   - Must demonstrate compliance with ToS
   - Must submit quota extension request
   - Audit takes weeks, plan ahead
2. OAuth scopes: youtube.upload (minimum) + youtube.readonly (analytics)
   - Incremental authorization: request scopes as needed
   - No youtube.force-ssl unless you need delete access
3. Token lifecycle management:
   - Access token: ~1 hour expiry → auto-refresh using refresh_token
   - Refresh token: persists until revoked or not used for 6 months
   - Store in scoped file (~/.creatorforge/channel_name/yt-token.json)
   - Each channel gets its own token store
4. Brand verification (Google OAuth consent screen audit):
   - Required for apps with >100 users
   - Submit for verification before going public
   - Can take 2-4 weeks for approval
```

## Recommended Project Structure

The current structure (`agent_core/`, `production/`, etc.) is **mostly correct** but needs reorganization to support the four-plane architecture. Recommended additions:

```
CreatorForge/
├── agent_core/
│   ├── analytics/           # REBUILD — see below
│   ├── publishing/          # REBUILD — see below
│   ├── recon/               # KEEP — mostly implemented
│   ├── scoring/             # KEEP — works, needs test coverage
│   └── quality/             # NEW — quality gate system
│       ├── gates.py          # Schema validation runner
│       ├── checks.py         # Domain checks (factual, brand, length)
│       └── review.py         # Human-in-the-loop approval
│
├── production/
│   ├── AudioGeneration/     # EXPAND — force alignment
│   ├── RenderEngine/        # EXPAND — multi-runtime support
│   ├── VisualGeneration/    # REBUILD — stubs → implementations
│   ├── MusicGeneration/     # NEW — BGM selection/generation
│   └── ComposeEngine/       # NEW — FFmpeg timeline builder
│
├── distribution/            # NEW — separate from production
│   ├── oauth.py              # OAuth token management
│   ├── uploader.py           # Resumable upload with retry
│   ├── scheduler.py          # Peak time calculation
│   ├── metadata.py           # SEO title/desc/tag generation
│   └── quota.py              # Quota tracker + budget manager
│
├── checkpoints/             # NEW — stage state persistence
│   └── {run_id}/
│       ├── production_order.json
│       ├── script.json
│       ├── audio_timeline.json
│       └── ...
│
├── analytics/               # REBUILD — stubs → implementations
│   ├── collector.py          # YouTube Analytics API
│   ├── insights.py           # Cross-channel aggregation
│   ├── brain_updater.py      # Learning weight evolution
│   └── scheduler.py          # When to collect (24h-after pattern)
│
└── quality/                  # Gate configuration
    ├── rules/                # YAML rules for quality checks
    └── gates/                # Schema + domain check configs
```

### Structure Rationale

- **`distribution/` separated from `production/`**: The OAuth/upload/schedule lifecycle is a distinct domain with different reliability requirements (network I/O, quota budgets) than media production. Mixing them couples API quota concerns with rendering concerns.
- **`checkpoints/` as first-class concept**: Checkpoints enable pipeline resumption after failure. Every stage writes a typed artifact before the next stage begins. Without checkpoints, a crash during upload means re-rendering the entire video.
- **`quality/` as a horizontal concern**: Quality gates (schema validation, brand checks, factual accuracy) apply across all planes, not just production. Having a dedicated module prevents gate logic from scattering across unrelated modules.
- **`analytics/` rebuilt with schedule awareness**: Analytics collection must be timed (24h+ after publish), batched (don't make an API call per video), and quota-aware. The current stub doesn't account for any of these.

## Architectural Patterns

### Pattern 1: Artifact-Driven Pipeline with Typed Checkpoints

**What:** Each pipeline stage consumes a typed JSON artifact and produces a new typed JSON artifact. Artifacts are schema-validated at stage boundaries. Checkpoints persist each artifact after successful validation — enabling resume from any stage.

**When to use:** Multi-stage production pipelines where stages can fail independently and re-running from scratch is expensive. This is the dominant pattern in Showrunner, CineMate, video_agent, and montage-ai.

**Trade-offs:**
- ✅ Resume from any stage — no wasted work on crash
- ✅ Each stage independently testable — mock inputs, assert outputs
- ✅ Clear data ownership — no shared mutable state
- ❌ Schema management overhead — need to maintain N artifact schemas
- ❌ Disk I/O for every stage — negligible for JSON, meaningful for binary assets

**Example:**
```python
# Typed artifact pattern using dataclasses
@dataclass
class ProductionOrder:
    topic: str
    channel: str
    script_style: str
    duration_seconds: int
    visual_style: str

@dataclass
class ScriptArtifact:
    title: str
    scenes: list[Scene]
    hooks: list[str]
    ctas: list[str]
    estimated_duration: float

class PipelineStage(ABC):
    """Base class for all pipeline stages."""
    @abstractmethod
    def execute(self, input_path: Path) -> Path:
        """Run stage, write artifact to checkpoints/, return artifact path."""
        pass

class ScriptStage(PipelineStage):
    def execute(self, input_path: Path) -> Path:
        order = load_artifact(input_path, ProductionOrderSchema)
        script = self._generate_script(order)
        validate_artifact(script, ScriptSchema)
        output_path = CHECKPOINTS_DIR / "script.json"
        save_artifact(script, output_path)
        return output_path
```

### Pattern 2: Multi-Provider Selector with Fallback Chain

**What:** Each capability (TTS, image gen, video rendering) has a selector that discovers available providers at runtime, ranks them by quality/cost/availability, and falls through the chain if the primary is unavailable. No hardcoded provider choices.

**When to use:** Any capability that has both free and paid options, or API-dependent functionality that must degrade gracefully. Used by OpenMontage (selector pattern), montage-ai (TTS fallback: Google Cloud → Edge → pyttsx3), and video_agent.

**Trade-offs:**
- ✅ Graceful degradation — pipeline never hard-blocks on a paid API being down
- ✅ Testable with mock providers
- ✅ Easy to add new providers — register, don't modify
- ❌ Testing matrix grows with provider count
- ❌ Provider ranking is subjective — needs periodic tuning

**Example:**
```python
class TTSSelector:
    """Selects TTS provider based on availability and quality."""
    providers: list[TTSProvider] = []

    def __init__(self):
        self.providers = [
            GoogleCloudTTS(),   # Primary: highest quality
            EdgeTTS(),          # Fallback 1: free, neural
            Pyttsx3TTS(),       # Fallback 2: offline, low quality
        ]

    def synthesize(self, text: str, voice: str) -> bytes:
        last_error = None
        for provider in self.providers:
            if not provider.available():
                continue
            try:
                return provider.synthesize(text, voice)
            except ProviderError as e:
                last_error = e
                continue
        raise AllProvidersFailed(last_error)
```

### Pattern 3: Quality Gate Graduation

**What:** Quality checks start in "dry-pass" mode — they log what they would flag without blocking output. After a probation period, successful checks graduate to "enforcement" mode (block on failure). Failed checks are either tuned or removed.

**When to use:** Any pipeline with automated quality checks where the cost of false positives (blocking good content) exceeds the cost of false negatives (publishing bad content). Used by the Leanboat self-improving content engine and LASEV's critique mechanism.

**Trade-offs:**
- ✅ Low-risk introduction of new checks — no sudden production blocking
- ✅ Data-driven tuning — only enforce checks that have proven value
- ✅ Easy to remove checks that never fire
- ❌ Requires a review cadence — checks pile up without review
- ❌ Dry-pass mode can create noise if thresholds are too sensitive

**Example:**
```python
class QualityGate:
    mode: Literal["dry", "enforce"]

    def check(self, artifact: dict) -> GateResult:
        violations = self._run_checks(artifact)
        if self.mode == "dry":
            log_violations(violations)
            return GateResult(pass_=True, note="Dry pass — would block on: ...")
        else:
            return GateResult(pass_=len(violations) == 0, violations=violations)

# Graduation lifecycle:
# 1. New check registered in "dry" mode
# 2. After 2 weeks: review violation log
# 3. If no false positives: graduate to "enforce"
# 4. If excessive false positives: tune threshold, keep in dry
# 5. If never fires in 4 weeks: remove check
```

### Pattern 4: Quota Budget Manager

**What:** A rate-limiter and budget tracker that sits in front of all YouTube API calls. Tracks daily quota consumption at the unit level, enforces per-channel budgets, and defers non-urgent operations when quota is low.

**When to use:** Any application making YouTube API calls — especially uploads (1,600 units each) or analytics collection where multiple channels are involved. Without this, a single debug loop can drain the entire 10,000-unit daily quota.

**Trade-offs:**
- ✅ Prevents silent quota exhaustion — degrades gracefully instead of 403 errors
- ✅ Enables quota-aware scheduling — defer uploads to next day if budget is tight
- ✅ Audit trail — know exactly which operations cost what
- ❌ Adds latency to every API call — the check itself is cheap but it's an extra hop
- ❌ State must persist across process restarts (file or DB)

**Example:**
```python
class QuotaBudget:
    """Daily quota budget for YouTube API operations."""

    DAILY_LIMIT = 10_000
    SAFETY_MARGIN = 500  # Reserve for critical operations

    COSTS = {
        "videos.insert": 1600,
        "videos.list": 1,
        "channels.list": 1,
        "search.list": 100,
        "analytics.list": 1,
    }

    def can_spend(self, operation: str) -> bool:
        cost = self.COSTS[operation]
        return (self._today_usage() + cost) <= (self.DAILY_LIMIT - self.SAFETY_MARGIN)

    def record(self, operation: str) -> None:
        self._log_operation(operation, self.COSTS[operation])

    def best_upload_time(self) -> datetime | None:
        """If remaining quota < 1600, suggest next-day upload."""
        remaining = self.DAILY_LIMIT - self.SAFETY_MARGIN - self._today_usage()
        if remaining < 1600:
            # Defer to next day (reset at midnight Pacific)
            return next_day_midnight_pacific()
        return None  # Can proceed now
```

### Pattern 5: Stage 1 / Stage 2 Rendering Split (Frames as Truth)

**What:** The render pipeline is split into two stages: Stage 1 generates still keyframes (cheap, easy to verify), Stage 2 animates between locked keyframes (expensive, done only after Stage 1 is approved). This is the core insight of Showrunner and is also visible in Bernini's planner/renderer split.

**When to use:** Any rendering pipeline where animation is expensive and visual consistency matters. Not needed for simple slideshow-style videos.

**Trade-offs:**
- ✅ Identity drift is caught at the still-image stage (cheap to fix)
- ✅ Re-rendering after edit only affects affected keyframes
- ✅ Clear approval gates — "approve this keyframe before we animate it"
- ❌ Two-pass rendering adds structural complexity
- ❌ Overkill for short-form content (<60s) where re-rendering is cheap

**Example flow:**
```
Script → Scene Plan
    │
    ▼
Stage 1: Generate Keyframes (still images)
    │  - Director agent plans shots
    │  - Storyboard agent renders still keyframes
    │  - Continuity agent checks consistency
    │  ← Human approval gate
    ▼
Stage 2: Animate (i2v between locked keyframes)
    │  - Animator agent creates video clips
    │  - Editor agent assembles final video
    ▼
Final output
```

## YouTube Upload Lifecycle

### OAuth 2.0 Authorization Code Flow

```
┌────────────┐         ┌────────────┐         ┌────────────┐
│ CreatorForge│         │   Google   │         │    User    │
│  (Python)  │         │   OAuth    │         │ (Channel   │
│            │         │   Server   │         │   Owner)   │
└─────┬──────┘         └─────┬──────┘         └─────┬──────┘
      │                      │                      │
      │  1. Auth Request     │                      │
      │  (client_id, scope,  │                      │
      │   redirect_uri,      │                      │
      │   access_type=offline)│                      │
      │─────────────────────►│                      │
      │                      │                      │
      │                      │  2. Consent Screen    │
      │                      │─────────────────────►│
      │                      │                      │
      │                      │  3. User Approves     │
      │                      │◄─────────────────────│
      │                      │                      │
      │  4. Auth Code         │                      │
      │◄─────────────────────│                      │
      │                      │                      │
      │  5. Exchange Code     │                      │
      │  (code + client_secret                      │
      │   + redirect_uri)    │                      │
      │─────────────────────►│                      │
      │                      │                      │
      │  6. Access + Refresh  │                      │
      │  Token Response      │                      │
      │◄─────────────────────│                      │
      │                      │                      │
      │  7. Store tokens in   │                      │
      │  ~/.creatorforge/     │                      │
      │  yt-token.json       │                      │
      │                      │                      │
      │  8. Use access token   │                      │
      │     (expires ~1 hour) │                      │
      │─────────────────────►│                      │
      │                      │                      │
      │  [Later, token expired]                      │
      │                      │                      │
      │  9. Refresh access    │                      │
      │  token (refresh_token)│                      │
      │─────────────────────►│                      │
      │                      │                      │
      │  10. New access token │                      │
      │◄─────────────────────│                      │
```

### Resumable Upload Protocol Steps

```
Step 1: INITIATE
  POST https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status
  Headers:
    Authorization: Bearer {access_token}
    Content-Type: application/json; charset=UTF-8
    X-Upload-Content-Length: {file_size_bytes}
    X-Upload-Content-Type: video/mp4
  Body:
    {"snippet": {"title": "...", "description": "...", "tags": [...], "categoryId": "22"},
     "status": {"privacyStatus": "private", "publishAt": "..."}}
  Response: 200 OK
    Location: {upload_url}  ← This is your session URI

Step 2: UPLOAD (single chunk)
  PUT {upload_url}
  Headers:
    Authorization: Bearer {access_token}
    Content-Length: {file_size_bytes}
    Content-Type: video/mp4
  Body: <binary video data>
  Response:
    200 OK → Upload complete. Response body contains video resource with `id`.
    308 Resume Incomplete → Range header tells you what was received.
    5xx → Retry with exponential backoff.
    404 → Session URI expired. Start over from Step 1.

Step 3: VERIFY
  GET https://www.googleapis.com/youtube/v3/videos?part=status&id={video_id}
  Headers:
    Authorization: Bearer {access_token}
  → Confirm processing status is "uploaded" or "processed"

KEY FACTS FOR PRODUCTION:
  - videos.insert costs 1,600 quota units per upload
  - schedule (publishAt) ONLY works with privacyStatus="private"
  - selfDeclaredMadeForKids is REQUIRED in status
  - Session URIs have finite lifetime — upload soon after initiating
  - Chunk size must be multiple of 256KB (last chunk exempt)
  - Default daily quota: 10,000 units → max ~6 uploads/day before optimization
  - Quota increase requires Google audit (takes 2-4 weeks, submit early!)
```

### Quota Management Strategy

```
Operation                       Cost     Daily Budget     Max/Day
─────────────────────────────────────────────────────────────
videos.insert (upload)         1,600    10,000 units       6
search.list                      100    10,000 units     100
videos.list (by ID, up to 50)     1    10,000 units  10,000
channels.list                      1    10,000 units  10,000
playlistItems.list                 1    10,000 units  10,000
analytics/reports.query            1    10,000 units  10,000

Budget Allocation (recommended for CreatorForge):
  Uploads:            3 × 1,600   = 4,800 units  (3 videos/day)
  Analytics fetch:   50 × 1       =    50 units  (per-video stats)
  Metadata lookups:  10 × 1       =    10 units  (category, trend data)
  Reserve:                        = 5,140 units  (safety margin)

Key optimizations:
  1. NEVER use search.list — use playlistItems.list instead (1 vs 100 units)
  2. Cache everything — video metadata, channel details, category IDs
  3. Batch video lookups — 50 IDs per videos.list call
  4. Use ETags for conditional requests (zero quota cost on 304)
  5. Track quota in a persistent QuotaBudget file
  6. Run batch uploads early in the Pacific day
  7. Set Cloud Monitoring alerts at 60% and 85% usage
```

### Scheduling Best Practices

```
Scheduling a video for future publish:
  1. Set privacyStatus = "private" in the upload request
  2. Set publishAt = ISO 8601 timestamp (e.g., "2026-07-11T14:00:00Z")
  3. YouTube automatically makes it public at publishAt
  4. NOT allowed: publishAt on "public" videos

Peak Time Calculation:
  - Use channel's own analytics to determine best publish time
  - Fallback: general YouTube peak hours (2-4 PM ET weekdays)
  - Consider timezone of target audience (from analytics)
  - Use analytics.reports.query to get subscriber activity times

Implementation for CreatorForge:
  scheduler.py should:
  - Pull channel analytics for subscriber activity patterns
  - Return optimal publish_at timestamp per channel
  - Consider: day of week + hour + timezone
  - Have fallback defaults when analytics are unavailable
  - Store calculated schedules in a queue for batch processing
```

## Analytics Feedback Loop

### Four-Phase Analytics Lifecycle

```
PHASE 1: COLLECT (24h after publish)
  │  YouTube Analytics API query:
  │    metrics: views, estimatedMinutesWatched, averageViewDuration,
  │             likes, dislikes, comments, shares, subscribersGained
  │    dimensions: day, video
  │  Cache result per video to avoid re-fetching
  │  Store in data/analytics/{video_id}.json
  ▼

PHASE 2: AGGREGATE (per-channel, weekly)
  │  Cross-video aggregation:
  │    - Per-topic performance (from topic JSONL match)
  │    - Per-pillar distribution & performance
  │    - Per-hook-type CTR estimation
  │    - Thumbnail performance correlation
  │  Store in data/insights/{channel_name}/weekly/
  ▼

PHASE 3: UPDATE BRAIN (weekly)
  │  Brain weight adjustment:
  │    - Topics that performed well → increase ICP weight
  │    - Pillars with high engagement → promote in scoring
  │    - Content formats with strong retention → add as signal
  │    - Competitor topics gaining traction → flag for recon
  │  Write updated learning_weights to agent-brain.json
  ▼

PHASE 4: RE-SCORE (on next discovery cycle)
  │  scoring/engine.py now uses updated weights:
  │    - icp_relevance: re-weighted by performance data
  │    - content_gap: re-calculated against updated brain
  │    - proof_potential: influenced by past performance
  │    - timeliness: unaffected (external signal)
  │  Result: topic scores now reflect "what actually works"
```

### Data Model

```json
{
  "analytics_entry": {
    "video_id": "abc123xyz",
    "channel": "ChannelA",
    "published_at": "2026-07-09T14:00:00Z",
    "collected_at": "2026-07-10T14:00:00Z",  // 24h after publish
    "metrics": {
      "views": 12500,
      "estimated_minutes_watched": 31250.5,
      "average_view_duration_seconds": 150.0,
      "likes": 450,
      "dislikes": 12,
      "comments": 38,
      "shares": 95,
      "subscribers_gained": 120
    },
    "topic_metadata": {
      "topic": "How to make AI videos",
      "pillar": "AI Tutorials",
      "hook_type": "statistical_tease",
      "score_at_production": 8.5
    }
  }
}
```

### Key Analytics Timing Rules

1. **Collect 24h after publish** — earlier data is noisy and may change significantly
2. **Aggregate weekly** — daily aggregation is too granular for content strategy decisions
3. **Brain update weekly, not per-video** — prevents overfitting to single-video noise
4. **Re-score on next discovery cycle** — don't retroactively re-score already-processed topics
5. **Minimum threshold: 3 videos per pillar before weight adjustment** — avoid reacting to outliers

## Modular Rendering Architecture

### Multi-Runtime Selector

```
RenderSpec.json
    │
    ▼
┌──────────────────────────────────────┐
│         Render Runtime Selector       │
│                                       │
│  Checks: available tools, complexity, │
│  desired output quality, asset types  │
└──┬───────────────┬─────────────────┬──┘
   │               │                 │
   ▼               ▼                 ▼
┌─────────┐  ┌─────────┐     ┌─────────┐
│ HYPER-  │  │ REMOTION│     │ FFMPEG  │
│ FRAMES  │  │ (React/ │     │ (simple │
│ (HTML/  │  │  Node)  │     │  cuts)  │
│ CSS/    │  │         │     │         │
│ GSAP)   │  │ Complex │     │ No      │
│         │  │ anims   │     │ anims   │
│ Kinetic │  │ + data  │     │ Trims   │
│ typo    │  │ viz     │     │ Concat  │
│ Overlays│  │ Lower   │     │ Caption │
│         │  │ thirds  │     │ overlay │
└─────────┘  └─────────┘     └─────────┘
```

### FFmpeg Timeline Builder (Primary for CreatorForge)

Given the current stack (Python, no Node.js dependency in production), **FFmpeg is the primary render runtime** with a declarative timeline abstraction:

```
Timeline:
  Scene 0: intro (5s)
    - background_image.jpg (Ken Burns zoom)
    - text_overlay: "AI Video Title" (fade in at 0s, fade out at 4s)
    - audio: narration_0.wav
    - music: bgm.mp3 (loop, -18dB)

  Scene 1: main (30s)
    - broll_1.mp4 (crop to 16:9, no audio)
    - captions from aligned_transcript.json (drawtext per word)
    - audio: narration_1.wav
    - music: bgm.mp3 (-18dB, continues from scene 0)

  Scene 2: outro (5s)
    - background_image.jpg (static)
    - text_overlay: CTA (slide in from bottom)
    - audio: narration_2.wav
    - music: bgm.mp3 (-18dB, fade out last 2s)

RENDER:
  → Single FFmpeg invocation with filter_complex
  → No frame data enters Python memory
  → ~30s for a 2-minute video (vs 4+ minutes with MoviePy pulling frames)

Key FFmpeg RenderConfig:
  - codec: libx264, preset: medium, crf: 20
  - pixel_format: yuv420p
  - audio: aac, 192k, 48000Hz
  - resolution: configurable (9:16 for Shorts, 16:9 for long-form)
```

### Render Pipeline Best Practices (from research)

| Practice | Source | Why |
|----------|--------|-----|
| Single FFmpeg invocation per render | video-arrange, montage-ai | MoviePy pulls frames into Python memory — 10x slower |
| Declarative timeline API | video-arrange, pyrector | filter_complex strings become unmaintainable past 3 clips |
| Configurable resolution/aspect | all systems | Must support 9:16 (Shorts), 16:9 (YouTube), 1:1 (Instagram) |
| Ken Burns effect on static images | VideoAutoPipeline, semantic foragecast | Prevents "static image" look without video generation |
| Crossfade transitions between scenes | VideoAutoPipeline, OpenMontage | xfade filter, avoid hard cuts between unrelated scenes |
| caption overlay via drawtext | video_agent, montage-ai | Uses aligned transcript for word-level sync |
| BGM mixing at -18dB | montage-ai | Prevents narration from being drowned out |
| Render preview (low-res) | semantic foragecast | Quick validation before full render |
| export_command() for reproducibility | video-arrange | Log the exact FFmpeg command for debugging |
| Frames-as-truth (Stage 1/Stage 2) | Showrunner | Expensive animation only after stills are approved |

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-10 channels | Current architecture is fine. SQLite for cache, file-based brain. Single-threaded pipeline. |
| 10-100 channels | Move to PostgreSQL for analytics. Add Celery/Redis for parallel render jobs. Implement quota budget manager per channel. Move beyond 10K quota — need Google audit. |
| 100+ channels | Distributed render farm (AWS Batch or similar). Event-driven pipeline (Pub/Sub between stages). Separate OAuth token management service. Dedicated analytics pipeline with time-series DB. |

### Scaling Priorities

1. **First bottleneck: YouTube API quota** — At 10K units/day and 1,600 per upload, you max out at ~6 uploads/day per project. Mitigation: QuotaBudget with scheduling, defer uploads, request quota extension early.

2. **Second bottleneck: Render parallelism** — Sequential renders bottleneck at ~2-3 min per video. Mitigation: Parallel render for channels whose assets are independent. Use asyncio.gather for audio+visual production stages.

3. **Third bottleneck: Analytics API calls** — Collecting analytics for 100+ videos daily burns quota fast. Mitigation: Cache aggressively, batch by video ID (50 per call), use ETags.

## Anti-Patterns

### Anti-Pattern 1: Linear Pipeline Without Checkpoints

**What people do:** Run the full pipeline from discovery to upload in one sequential process. If it crashes during upload, they restart from discovery.

**Why it's wrong:** Re-running LLM calls (costly), re-scraping assets (API rate limits), and re-rendering (compute time) on every crash. For a 5-minute render + 3-minute upload, a crash at 99% costs 8 minutes of re-do time.

**Do this instead:** Every stage writes a typed, schema-validated artifact to a `checkpoints/` directory. The orchestrator checks if a checkpoint exists before running a stage. `ScriptStage` checks for `checkpoints/script.json` before calling the LLM again.

### Anti-Pattern 2: Hardcoded API Providers

**What people do:** `TTS = GoogleCloudTTS(api_key=HARDCODED_KEY)`. When the key quota is exhausted or the API changes, the pipeline breaks silently.

**Why it's wrong:** Single point of failure. No graceful degradation. In the current codebase, `tts_generation.py` has a hardcoded proxy URL and API key — exactly this anti-pattern.

**Do this instead:** Multi-provider selector with fallback chain. Primary → fallback → offline fallback. Register providers, harden the selectors logging so you know when fallbacks are invoked.

### Anti-Pattern 3: Uploading Without Quota Check

**What people do:** Build a full pipeline, upload 7 videos in a day, then hit `403 quotaExceeded` and the channel can't upload for 24 hours.

**Why it's wrong:** The quota error is thrown mid-upload (after spending the 1,600 units and the time). The video data was transmitted but never processed. The quota is consumed regardless of success.

**Do this instead:** Check `QuotaBudget.can_spend("videos.insert")` before the upload starts. If budget is insufficient, schedule the upload for the next day. Log pending uploads to a queue.

### Anti-Pattern 4: Fetching Analytics Too Early

**What people do:** Collect analytics immediately after publish. The data is noisy, misleading, and changes significantly in the first 24 hours.

**Why it's wrong:** Early data floods the analytics store with unreliable metrics. The brain updater weights get pulled toward noise. Content decisions are made on statistically insignificant data.

**Do this instead:** Enforce a minimum 24-hour delay before analytics collection. Use a scheduler: `collect_at = publish_at + timedelta(hours=24)`. Batch collections don't poll.

### Anti-Pattern 5: Single FFmpeg Invocation Per Scene (MoviePy-style)

**What people do:** Use MoviePy or similar to process each scene individually — render scene N, load it into Python memory, manipulate numpy arrays, then write scene N+1. Everything is stitched at the end.

**Why it's wrong:** 4+ minutes for a 2-minute video because every frame is decoded into Python memory, processed, and re-encoded. The per-scene approach multiplies encoding overhead (each scene has its own keyframe, and stitching re-encodes again).

**Do this instead:** Build all filter operations into a single `filter_complex` graph and call FFmpeg once. The `video-arrange` library demonstrates this: declarative timeline → single filter complex → single ffmpeg call. No frame data enters Python.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **YouTube Data API v3** | OAuth 2.0 (offline access) + resumable upload | 10K units/day default. 1,600 per upload. Request audit extension early. |
| **YouTube Analytics API** | Same OAuth credentials. `reports.query` endpoint. | 1 unit per query. Minimum 24h delay after publish. |
| **Google Gemini TTS** | HTTP POST to API endpoint (or proxy) with API key | Currently hardcoded — move to env var + multi-provider fallback |
| **Pexels API** | REST API with free API key | Search by keyword. Rate limited. Cache results aggressively. |
| **Pixabay API** | REST API with free API key | Alternative image source. Same caching considerations. |
| **Freesound / Pixabay SFX** | REST API | For sound effects. Consider building a local SFX library over time. |
| **MusicGen** | Local model (facebook/musicgen-small) | GPU required for real-time. Cache by mood. Model loads once per run. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Scoring ↔ Agent Brain | File I/O (read brain.json, write brain.json) | Read-only in scoring engine, write-only in brain_updater. No concurrent writes. |
| Production ↔ Distribution | File I/O (render artifact → checkpoints/) | Distribution reads the rendered video path from checkpoint. No direct coupling. |
| Distribution ↔ Analytics | File I/O (publish_log.json → analytics collector) | Analytics collector reads publish log to know which videos to check. |
| Analytics ↔ Agent Brain | File I/O (write updated brain.json) | Single writer pattern — analytics/brain_updater.py is the only writer of learning_weights. |
| All stages ↔ Checkpoints | File I/O (typed JSON artifacts) | Artifacts are the contract between stages. Schema validated at read. |

## Sources

- Google Project Montage — https://github.com/google/project-montage (MEDIUM confidence: training data)
- CineMate Architecture — https://github.com/lamwimham/CineMate (MEDIUM: single project, well-documented)
- Showrunner Architecture — https://github.com/divi-vijayakumar/Showrunner (HIGH: official architecture docs)
- OpenMontage Architecture — https://github.com/calesthio/OpenMontage/blob/main/docs/ARCHITECTURE.md (HIGH: official docs)
- LASEV (Multi-Agent Educational Video) — arXiv:2602.11790 (HIGH: peer-reviewed paper)
- montage-ai Architecture — https://github.com/AliHamzaAzam/montage-ai (MEDIUM: single project)
- YouTube Upload API Guide — https://developers.google.com/youtube/v3/guides/uploading_a_video (HIGH: official Google docs)
- Resumable Upload Protocol — https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol (HIGH: official Google docs)
- YouTube OAuth 2.0 — https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps (HIGH: official Google docs)
- YouTube Quota Calculator — https://developers.google.com/youtube/v3/determine_quota_cost (HIGH: official Google docs)
- YouTube Quota Limits Guide 2026 — https://outlierkit.com/resources/youtube-api-quota/ (MEDIUM: third-party, verified against official)
- 4-Plane Architecture for AI Content Engineering — https://generativeai.pub/the-4-plane-architecture-of-ai-native-content-engineering (HIGH: detailed architecture analysis)
- Self-Improving Content Engine — https://www.leanboat.io/blog/self-improving-content-engine (HIGH: real-world implementation guide)
- Closed Loop Content Strategy — https://floyi.com/playbook/closed-loop-content-strategy/ (MEDIUM: vendor perspective, sound architecture)
- video-arrange FFmpeg Timeline Builder — https://github.com/tomastimelock/video-arrange (HIGH: documented architecture, well-tested approach)
- video_agent Architecture — https://github.com/hyang0129/video_agent (MEDIUM: single project, artifact-driven pattern)
- Semantic Foragecast Engine — https://github.com/semanticintent/semantic-foragecast-engine/blob/main/ARCHITECTURE.md (HIGH: well-documented four-phase pipeline)
- pyrector Declarative Video Builder — https://github.com/LeandroBarone/pyrector (MEDIUM: emerging library, sound pattern)
- YouTube API Squeezing Lessons — https://dev.to/qcrao/what-i-learned-squeezing-the-youtube-data-api-v3-quota-for-a-side-project (HIGH: real-world quota optimization)
- Content Feedback Loops — https://digitalmoose.ai/feedback-loops-content-strategy/ (MEDIUM: general overview, sound principles)

---
*Architecture research for: AI Content Creation / Video Publishing Pipeline*
*Researched: 2026-07-10*
