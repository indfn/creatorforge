# Codebase Structure

**Analysis Date:** 2026-07-10

## Directory Layout

```
CreatorForge/
├── .agents/                     # 🔷 Canonical source for agent config (commands + skills)
│   ├── commands/                #   AI CLI commands (/viral:*)
│   └── skills/                  #   23+ agent skills (hyperframes, last30days, etc.)
├── .claude/                     # Claude Code config (symlinks → .agents/)
├── .opencode/                   # OpenCode config (symlinks → .agents/)
├── .planning/                   # GSD planning artifacts (codebase maps, roadmaps)
├── agent_core/                  # 🧠 Core Python engine
│   ├── analytics/               #   Performance data + brain evolution
│   ├── publishing/              #   YouTube upload + OAuth + scheduling
│   ├── recon/                   #   🕵️ Competitor intelligence (largest module)
│   │   ├── scraper/             #     Instagram/YouTube scrapers
│   │   ├── skeleton_ripper/     #     LLM-based content analysis pipeline
│   │   ├── storage/             #     SQLite asset/collection models
│   │   ├── utils/               #     Logger, retry, state manager
│   │   └── web/                 #     Flask Recon UI (templates + static)
│   └── scoring/                 #   Topic/angle scoring engine
├── assets/                      # Brand assets (logos, previews)
├── channels/                    # 📺 Per-channel directories
│   └── ChannelA/                #   Default channel
│       ├── active_production/   #     Working dir: assets/ + render/
│       ├── data/                #     analytics/ hooks/ insights/ recon/ topics/
│       ├── brain.json           #     Channel-specific brain
│       └── channel_config.json  #     YouTube + TTS + render config
├── data/                        # 💾 Central data stores
│   ├── analytics/               #   Raw analytics data
│   ├── hooks/                   #   Hook repository
│   ├── insights/                #   Cross-channel insights
│   ├── recon/                   #   Recon data (competitors, reports, cache, logs)
│   │   ├── cache/               #     Transcript cache
│   │   ├── competitors/         #     Per-competitor scraped data
│   │   ├── logs/                #     Structured JSON logs
│   │   └── reports/             #     Skeleton analysis reports
│   ├── agent-brain.json         #   🧠 Central brain (ICP, pillars, competitors)
│   └── cta-templates.json       #   CTA template library
├── docs/                        # Documentation
├── production/                  # 🎬 Video/audio production pipeline
│   ├── AudioGeneration/         #   TTS generation + force alignment
│   ├── RenderEngine/            #   Linting + HTML scene templates
│   │   ├── system_assets/       #     Render system assets (empty)
│   │   └── templates/           #     Scene HTML templates (chart, default, broll, split)
│   └── VisualGeneration/        #   Asset scraping + fallback generation
├── schemas/                     # JSON Schema draft-07 contracts
├── scripts/                     # Bash + Python utility scripts
│   ├── init-creatorforge.sh     #   Bootstrap script
│   ├── run-recon-ui.sh          #   Launch Recon UI
│   ├── fetch-yt-analytics.py    #   YouTube Analytics fetcher
│   ├── fetch-ig-insights.py     #   Instagram Insights fetcher
│   ├── generate-pdf.py          #   PDF lead magnet generator
│   ├── setup-yt-oauth.py        #   YouTube OAuth setup
│   └── setup-ig-token.py        #   Instagram token setup
├── .env.example                 # Environment variable template
├── requirements.txt             # Python dependencies
└── README.md                    # Project overview + commands
```

## Directory Purposes

**`.agents/`:**
- Purpose: Canonical source for AI CLI commands and agent skills
- Contains: Command markdown files (`viral-*.md`), 23+ skill subdirectories
- Key files: `.agents/commands/viral-setup.md`, `.agents/commands/viral-discover.md`
- Note: `.claude/` and `.opencode/` directories symlink into this directory

**`agent_core/recon/`:**
- Purpose: Largest module — competitor intelligence pipeline from scraping to topic generation
- Contains: Scrapers (Instagram/YouTube), skeleton analysis pipeline, storage layer, Flask web UI
- Key files:
  - `scraper/instagram.py`: `InstaClient` — Instaloader-based IG scraper (242 lines)
  - `scraper/youtube.py`: YouTube channel video fetcher
  - `skeleton_ripper/pipeline.py`: `SkeletonRipperPipeline` — 5-stage analysis orchestrator (455 lines)
  - `skeleton_ripper/llm_client.py`: `LLMClient` — multi-provider LLM abstraction (203 lines)
  - `skeleton_ripper/extractor.py`: `BatchedExtractor` — batch JSON extraction from LLM (142 lines)
  - `skeleton_ripper/cache.py`: `TranscriptCache` — filesystem transcript caching (98 lines)
  - `bridge.py`: skeleton→topic conversion, scoring integration (244 lines)
  - `config.py`: `ReconConfig` — credential/env/config management (182 lines)
  - `tracker.py`: deduplication state for competitor processing (141 lines)
  - `storage/database.py`: SQLite init + connection management (104 lines)
  - `storage/models.py`: `Asset`, `Collection` dataclass ORM (195 lines)
  - `utils/logger.py`: `ReconLogger` — singleton structured logger (197 lines)
  - `web/app.py`: Flask Recon UI — dashboard, skeleton ripper, settings (385 lines)

**`agent_core/analytics/`:**
- Purpose: Stub implementations for analytics collection and brain evolution
- Contains: `collector.py`, `insights.py`, `brain_updater.py`
- Key files: All raise `NotImplementedError` — placeholder for future implementation

**`agent_core/scoring/`:**
- Purpose: Topic scoring against agent brain ICP and learning weights
- Key files: `engine.py` (292 lines — pure functions, no side effects), `rescore.py` (132 lines — CLI utility)

**`agent_core/publishing/`:**
- Purpose: YouTube publishing pipeline with stubs for most features
- Key files: `uploader.py` (42 lines — CLI argument parser + stub), `oauth.py`, `scheduler.py`, `metadata.py`

**`production/`:**
- Purpose: Video content production pipeline
- Contains:
  - `AudioGeneration/tts_generation.py` (174 lines — Gemini 3.1 Flash TTS CLI)
  - `AudioGeneration/force_align.py` (34 lines — stub)
  - `RenderEngine/linter.py` (85 lines — pre-render validation)
  - `RenderEngine/templates/` (4 HTML scene templates)
  - `VisualGeneration/asset_scraper.py` (stub), `sfx_scraper.py` (stub), `fallback_cli.py` (stub)

**`channels/`:**
- Purpose: Per-channel configuration and data isolation
- Key files: `channel_config.json` (YouTube, TTS, render settings), `brain.json` (per-channel brain)

**`schemas/`:**
- Purpose: JSON Schema draft-07 contracts for all pipeline data types
- Key files: `topic.schema.json`, `script.schema.json`, `angle.schema.json`, `hook.schema.json`, `production-order.schema.json`, `analytics-entry.schema.json`, `channel-config.schema.json`, `agent-brain.schema.json`, `insight.schema.json`, `swipe-hook.schema.json`, `competitor-reel.schema.json`, `hyperframe.schema.json`

**`scripts/`:**
- Purpose: Standalone utility scripts for setup, data fetching, and operations
- Naming: `{action}-{target}.{sh|py}` pattern

## Key File Locations

**Entry Points:**
- `agent_core/recon/web/app.py`: Flask Recon UI (main web interface)
- `agent_core/publishing/uploader.py`: YouTube upload CLI (`python3 -m agent_core.publishing.uploader --channel ChannelA`)
- `agent_core/scoring/rescore.py`: Topic rescore CLI (`python3 agent_core/scoring/rescore.py`)
- `scripts/init-creatorforge.sh`: Full project bootstrap
- `.agents/commands/viral-*.md`: AI CLI command entry points

**Configuration:**
- `data/agent-brain.json`: Central brain state
- `.env.example`: Environment variable template (creates `.env` on init)
- `channels/{name}/channel_config.json`: Per-channel YouTube/TTS config
- `channels/{name}/brain.json`: Per-channel brain state
- `requirements.txt`: Python dependencies

**Core Logic:**
- `agent_core/recon/skeleton_ripper/pipeline.py`: Skeleton analysis pipeline
- `agent_core/recon/bridge.py`: Recon-to-topic integration
- `agent_core/scoring/engine.py`: Topic scoring engine
- `agent_core/recon/config.py`: Credential/config management
- `agent_core/recon/scraper/instagram.py`: Instagram scraper
- `production/AudioGeneration/tts_generation.py`: TTS audio generation
- `production/RenderEngine/linter.py`: Pre-render validation

**Testing:**
- No test files detected in the codebase
- Some modules have `__pycache__/` directories indicating local runs

**Databases:**
- `data/recon/recon.db`: SQLite database (asset management)
- `data/recon/tracker-state.json`: JSON state (content dedup)
- `data/topics/*-topics.jsonl`: JSONL data (scored topics)

## Naming Conventions

**Files:**
- Python: `snake_case.py` (e.g., `tts_generation.py`, `force_align.py`, `brain_updater.py`)
- Shell: `kebab-case.sh` (e.g., `init-creatorforge.sh`, `run-recon-ui.sh`, `refresh-ig-token.sh`)
- JSON Schema: `kebab-case.schema.json` (e.g., `topic.schema.json`, `channel-config.schema.json`)
- Templates: `kebab-case.html` (e.g., `skeleton_ripper.html`, `chart-overlay.html`)
- Data files: `{date}-topics.jsonl` (e.g., `20260304-topics.jsonl`)

**Directories:**
- Python packages: `snake_case/` (e.g., `skeleton_ripper/`, `system_assets/`)
- Config dirs: `UpperFirst/` for channels (`ChannelA/`, `Default/`)
- Top-level: `kebab-case/` or single word (`agent_core/`, `production/`, `schemas/`)

**Functions:**
- Python: `snake_case()` (e.g., `generate_topics_from_skeletons()`, `load_brain_context()`, `score_icp_relevance()`)
- Class methods follow same convention

**Classes:**
- Python: `PascalCase` (e.g., `SkeletonRipperPipeline`, `BatchedExtractor`, `TranscriptCache`, `ReconLogger`, `InstaClient`, `LLMClient`, `Asset`, `Collection`)

**Variables:**
- Python: `snake_case` (e.g., `brain_ctx`, `learning_weights`, `video_path`, `error_code`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `BRAIN_FILE`, `ACTION_KEYWORDS`, `MIN_TRANSCRIPT_WORDS`)

## Where to Add New Code

**New Feature:**
- Primary code: `agent_core/{module_name}/` (analytics, publishing, recon, scoring)
- Tests: No test directory exists — would need to create `tests/` at project root or co-located `test_*.py`

**New Module/Subsystem:**
- Implementation: Create new directory under `agent_core/` with `__init__.py` exporting key classes/functions
- Schema: `schemas/{name}.schema.json`
- Data storage: `data/{name}/` for JSONL/JSON data

**New Scraper/Data Source:**
- Scraper class: `agent_core/recon/scraper/{platform}.py` (follow `instagram.py` / `youtube.py` pattern)
- CLI command: `.agents/commands/viral-{name}.md`

**New Production Component:**
- Audio: `production/AudioGeneration/{name}.py`
- Visual: `production/VisualGeneration/{name}.py`
- Render template: `production/RenderEngine/templates/{name}.html`

**New Channel:**
- Config: `channels/{Name}/channel_config.json`
- Brain: `channels/{Name}/brain.json`
- Data dirs: `channels/{Name}/data/{analytics,hooks,insights,recon,topics}/`
- Production: `channels/{Name}/active_production/{assets,render}/`

**New Script:**
- Python: `scripts/{action}-{target}.py`
- Shell: `scripts/{action}-{target}.sh`

**Utilities:**
- Shared helpers: `agent_core/recon/utils/` (for logging, retry, state management)

## Special Directories

**`__pycache__/`:**
- Purpose: Python bytecode cache
- Generated: Yes (by Python interpreter)
- Committed: No (in `.gitignore`)

**`data/recon/cache/`:**
- Purpose: Filesystem transcript cache for competitor videos
- Generated: Yes (at runtime during skeleton analysis)
- Committed: No (transient cache data)
- Format: `{platform}_{username}_{video_id}.txt`

**`data/recon/reports/`:**
- Purpose: Skeleton analysis output reports organized by job run
- Generated: Yes (per skeleton ripper run)
- Committed: No (run artifacts)
- Format: `{timestamp}_{jobid}/` containing `skeletons.json`, `synthesis.json`, `report.md`

**`data/topics/`:**
- Purpose: Daily scored topic exports as JSONL
- Generated: Yes (from `/viral:discover` or bridge pushes)
- Committed: Yes (source of truth for topic pipeline)
- Format: `{YYYYMMDD}-topics.jsonl`

**`channels/{name}/active_production/`:**
- Purpose: Working directory for in-progress video production
- Generated: Yes (per production run)
- Committed: No (transient build artifacts)
- Contains: `active_script.json`, `aligned_transcript.json`, `assets/`, `render/`

---

*Structure analysis: 2026-07-10*
