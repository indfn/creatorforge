---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_plan: 0
status: complete
last_updated: "2026-07-28T00:00:00.000Z"
progress:
  total_phases: 14
  completed_phases: 14
  total_plans: 42
  completed_plans: 42
  percent: 100
---

# CreatorForge — Project State

## Project Reference

**Core Value:** One command from idea to published video: discover competitor patterns → generate script → produce video → publish → learn from results.

**Description:** AI-powered content creation suite for OpenCode/Claude Code. Publishes winning content by discovering competitor patterns, generating scripts, producing video, and learning from performance — all through agent commands.

**Current Focus:** All 14 phases complete. v1.0 milestone delivered.

---

## Current Position

| Field | Value |
|-------|-------|
| **Milestone** | v1 |
| **Current Phase** | 14 — Agent Documentation |
| **Status** | Complete |
| **Progress** | Phase 14/14 — All phases complete |

```
Phase 1:  [##########] 100% ✓
Phase 2:  [##########] 100% ✓
Phase 3:  [##########] 100% ✓
Phase 4:  [##########] 100% ✓
Phase 5:  [##########] 100% ✓
Phase 6:  [##########] 100% ✓
Phase 7:  [##########] 100% ✓
Phase 8:  [##########] 100% ✓
Phase 9:  [##########] 100% ✓
Phase 10: [##########] 100% ✓
Phase 11: [##########] 100% ✓
Phase 12: [##########] 100% ✓
Phase 13: [##########] 100% ✓
Phase 14: [##########] 100% ✓
```

---

## Performance Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Phases completed | 14/14 | 14/14 |
| Plans completed | 42/42 | 42/42 |
| Requirements covered | 89/89 | 89/89 |

---
| Phase 02 P01 | 5m | 3 tasks | 2 files |
| Phase 02 P03 | 12m | 3 tasks | 3 files |
| Phase 02 P02 | 12min | 1 tasks | 1 files |
| Phase 03 P01 | 8 | 1 tasks | 3 files |
| Phase 03-test-framework P03 | 12 | 3 tasks | 2 files |
| Phase 03-test-framework P04 | 12 | 3 tasks | 1 files |
| Phase 03-test-framework P05 | 5 | 3 tasks | 2 files |
| Phase 03-test-framework P06 | 6m | 28 tasks | 2 files |
| Phase 04-ci-pipeline P01 | 12m | 2 tasks | 4 files |
| Phase 04-ci-pipeline P02 | 8min | 2 tasks | 2 files |
| Phase 04-ci-pipeline P04 | 5m | 1 task | 2 files |
| Phase 04-ci-pipeline P03 | 15min | 1 tasks | 3 files |
| Phase 05-channel-onboarding-branding P01 | 300 | 2 tasks | 4 files |
| Phase 05-channel-onboarding-branding P03 | 5m | 3 tasks tasks | 3 files files |
| Phase 06-youtube-publishing P01 | 15m | 2 tasks | 1 files |
| Phase 06-youtube-publishing P03 | 12min | 1 tasks | 1 files |
| Phase 06-youtube-publishing P02 | 15m | 2 tasks | 1 files |
| Phase 07-analytics-collection-storage P01 | 8m | 3 tasks | 2 files |
| Phase 07-analytics-collection-storage P02 | 12m | 2 tasks | 1 files |
| Phase 08-brain-evolution-loop P08-01 | 190s | 2 tasks tasks | 2 files files |
| Phase 08-brain-evolution-loop P08-02 | 3m52s | 2 tasks | 2 files |
| Phase 10-visual-asset-pipeline P01 | 58min | 3 tasks | 10 files |
| Phase 10-visual-asset-pipeline P02 | 12min | 2 tasks | 2 files |
| Phase 10-visual-asset-pipeline P03 | 12min | 3 tasks tasks | 5 files files |
| Phase 10-visual-asset-pipeline P04 | 12min | 1 tasks | 1 files |
| Phase 12-recon-efficiency-rework P01 | 15 | 3 tasks | 7 files |
| Phase 12-recon-efficiency-rework P03 | 495 | 77 tasks | 5 files |
| Phase 12-recon-efficiency-rework P02 | 8min | 4 tasks | 3 files |
| Phase 13-onboarding-infrastructure P01 | 25min | 10 gaps | 17 files |
| Phase 14-agent-documentation P01 | 5m | 1 task | 1 file |
| Phase 14-agent-documentation P02 | 8m | 3 tasks | 7 files |
| Phase 14-agent-documentation P03 | 3m | 2 tasks | 3 files |

## Accumulated Context

### Key Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Phase 1 = Pipeline Infrastructure first | Checkpoints, quality gates, and QuotaBudget are horizontal dependencies for all other phases |
| 2 | Phase 2 = Security before new features | Fix hardcoded keys, debug mode, plaintext credentials before adding upload/analytics capabilities |
| 3 | Phases 3-4 = Tests before new features | Comprehensive test coverage for existing code before implementing stubs/features |
| 4 | Phase 5 = Publishing early | Critical path — highest user-visible value; Google quota audit started in Phase 1 to unblock |
| 5 | Phases 6-7 = Analytics after publishing | Need published videos before analytics collection can function |
| 6 | Phases 8-9 = Audio + Visual in parallel | No data dependency between audio and visual production pipeline |
| 7 | Phase 10 = Video Rendering last | Requires both audio (Phase 8) and visual assets (Phase 9) as inputs |
| 8 | PIPE-04 (QuotaBudget shared service) in Phase 1 | Foundation service; PUBLISH-03 (QuotaBudget for publishing) in Phase 5 consumes it |
| 9 | Phase 2 split into 3 plans | 02-01: packaging + env vars + dead code; 02-02: Fernet encryption; 02-03: Flask hardening + sys.path cleanup |
| 10 | Used frozenset for SETTINGS_WHITELIST | Immutable, hashable, clearly communicates it shouldn't be modified at runtime |
| 11 | Rejected keys as warning, not error | Partial updates with valid keys still succeed |
| 12 | Kept import sys in rescore.py | sys.argv and sys.exit() used throughout the file |
| 13 | Empty/null values silently skipped in settings API | Preserves existing partial-update behavior |
| 14 | All pytest config in pyproject.toml — single source of truth | No pytest.ini or .coveragerc files needed |
| 15 | Fixtures use tmp_path (built-in) instead of tempfile | pytest-managed cleanup, no orphaned temp dirs |
| 16 | agent_core imports inside fixture function bodies | Prevents import-time side effects in test infra |
| 17 | All fixtures autouse=False | Tests must explicitly request dependencies |
| 18 | Mocked bridge.engine_score_topic in bridge tests | Avoids coupling to engine internals while verifying is_competitor flag; cleaner than patching engine.BRAIN_FILE |
| 19 | Row index correction in Analytics API response | With dimensions="video", row[0]=video_id, shifting metric indices by 1 from plan spec |
| 20 | estimated_minutes_watched excluded from metrics dict | Schema has additionalProperties: false, field not in schema properties |
| 21 | Path traversal protection in persist_entry | _sanitize_content_id() strips path separators per T-07-01 |
| 22 | Timestamp comparison uses Python ISO format strings | Avoids microsecond precision mismatch with SQLite datetime('now') |
| 23 | threading.Lock over file-level portalocker for SQLite | Sufficient for single-process with WAL mode + busy_timeout |
| 24 | Per-scene blueprint generates GSAP-powered HyperFrames compositions | Follows `.agents/skills/hyperframes-core/` contract (data-* attributes, paused GSAP timeline, seekable tweens, direct-root video children) — not CSS @keyframes or requestAnimationFrame. Fully compatible with `npx hyperframes {lint,validate,preview,render}`. |
| 25 | YouTube caption-first extraction via yt-dlp | `get_video_captions()` uses `yt-dlp --skip-download --write-auto-subs --sub-lang` — free, instant, no Whisper API cost. Falls through to download+transcribe only when captions are absent/invalid. |
| 26 | Instagram caption-as-transcript | Reel captions ≥ 10 words used directly as transcripts; skip download+transcribe for those posts. Caption recorded with `source="instagram_caption"`. |
| 27 | Groq Whisper API as default transcription provider | Free tier (`whisper-large-v3-turbo`), OpenAI-compatible endpoint. Fallback chain: Groq → local faster-whisper. `transcribe_provider` defaults to `"groq"` in config.py. |
| 28 | SQLite-backed transcript cache replaces flat files | `DbTranscriptCache` with TTL eviction (30d default), `migrate_from_flat_cache()` copies existing `.txt` files on first run. Original `TranscriptCache` deprecated with `DeprecationWarning`. |
| 29 | Transcript cleaning module | `clean_transcript(raw, source)` handles YouTube VTT artifacts (`[Music]`, bracket content, timings), Whisper incomplete sentences, Instagram Unicode quotes. `is_valid_transcript()` enhanced with `min_words`/`min_word_length` params. |
| 30 | Onboarding fixed as prerequisite to Agent Documentation | 10 gaps identified (broken install.sh, bifurcated bootstraps, no doctor CLI, no .env auto-fill, manual IG OAuth, no Fernet key backup, missing cron scripts/plists, stale CRON-SETUP.md, fragile scripts/__init__.py, stale init-creatorforge.sh) — all fixed in one pass before Phase 14 |
| 31 | `creatorforge doctor` as standalone CLI entrypoint | `scripts/doctor.py` registered in `pyproject.toml` as `creatorforge-doctor`. Checks 19 items across 6 categories: project structure, CLI tools, API keys, credential encryption, OAuth tokens, network. Supports `--quiet` and `--fix` flags. |
| 32 | `.env` setup is now interactive with browser links | `scripts/setup-env.py` walks through 8 key groups (LLM, Groq, YouTube, Instagram, TTS, Pexels, Pixabay, Freesound). Opens signup URLs in browser for each missing key, saves to `.env`. `--check` mode shows missing keys only. |
| 33 | IG OAuth now supports automatic redirect capture | `scripts/setup-ig-token.py` starts a local HTTP server (port 8199) by default, opens Facebook OAuth URL in browser, catches redirect automatically. `--manual` flag preserves legacy copy-paste behavior. |
| 34 | Fernet key backup into .env | `scripts/backup-credentials-key.py --to-env` writes `CREDENTIALS_ENCRYPTION_KEY` into `.env`. `--export` prints to stdout for password manager backup. Without backup, losing `data/recon/credentials.key` makes all encrypted creds unrecoverable. |
| 35 | Cron scripts and launchd plists created from scratch | `scripts/daily-discover.sh` and `scripts/weekly-analyze.sh` were documented but missing — created with dry-run support and proper logging. `scripts/install-crons.sh` and `scripts/uninstall-crons.sh` manage macOS launchd plists. `cron/` directory holds plist templates with `__PIPELINE_DIR__` placeholder resolved at install time. |
| 36 | AGENTS.md as universal agent playbook | AGENTS.md at project root is the single entry point for any AI CLI (OpenCode, Claude Code, Codex). Per-stage deep-dive docs in `.agents/docs/` provide executor-level detail. `.agents/` is the canonical source; `.opencode/` and `.claude/` symlink back for compatibility. |

### Active Todos

- ✅ Phase 13 complete: 10 onboarding gaps fixed, 9 new files (doctor.py, setup-env.py, setup-ig-token.py, backup-credentials-key.py, daily-discover.sh, weekly-analyze.sh, install-crons.sh, uninstall-crons.sh, 2 plist templates)
- ✅ Phase 14 complete: AGENTS.md playbook + 7 per-stage docs + agent prompt update + README tool compat section

### Blockers

- None currently — v1.0 milestone complete

---

## Repository Structure

```
.planning/
├── PROJECT.md          — Project overview, constraints, decisions
├── REQUIREMENTS.md     — v1/v2 requirements with IDs
├── ROADMAP.md          — Phase structure, success criteria, dependencies
├── STATE.md            — This file — project state and continuity
├── config.json         — GSD workflow configuration
├── research/
│   ├── SUMMARY.md      — Research findings and phase recommendations
│   ├── STACK.md        — Recommended technology stack
│   ├── FEATURES.md     — Feature landscape analysis
│   ├── ARCHITECTURE.md — Architecture approach from research
│   └── PITFALLS.md     — Critical pitfalls and mitigations
└── codebase/
    ├── ARCHITECTURE.md — Current codebase architecture analysis
    └── CONCERNS.md     — Tech debt, security, performance concerns
```

---

*Last updated: 2026-07-28 — Phase 14 (Agent Documentation) complete: AGENTS.md playbook, 7 per-stage docs, agent prompt update, README tool compat; v1.0 milestone complete*
