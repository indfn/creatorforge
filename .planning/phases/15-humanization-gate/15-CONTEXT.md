# Phase 15: Humanization Gate — Context

**Gathered:** 2026-08-14
**Status:** Complete

<domain>
## Phase Boundary

AI-written scripts and publish metadata must read as human-written before they advance through the pipeline. The `humanize` skill is applied during generation and the `ai-check` skill is used as an exactly-once quality checkpoint before anything persists (Script stage) or uploads (Publish stage).

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**5 requirements are locked.** See `15-SPEC.md` for full requirements, boundaries, and acceptance criteria.

**In scope (from SPEC.md):**
- `humanize` + `ai-check` skills installed canonically in `.agents/skills/` with MIT attribution
- Symlinks into `.claude/skills/` and `.opencode/skills/` (existing pattern)
- Script-stage Humanization Gate: humanize during generation → ai-check exactly once → on fail humanize once more (max 2 passes, no re-check)
- Publish-stage Metadata Humanization Gate (title/description/CTA)
- Voice matching via `channels/{name}/voice/` for writer-profile distillation
- Enforcement: AGENTS.md, per-stage docs, viral-script (Phase E.5), publish-video command, viral-pipeline agent, opencode.json, doctor, setup

**Out of scope (from SPEC.md):**
- Re-architecting `.claude/` / `.opencode/` (symlink pattern preserved as-is)
- Creating new pipeline stages or pipeline code changes
- Modifying the humanize/ai-check skill content (vendored upstream)

</spec_lock>

<decisions>
## Implementation Decisions

- **D-01:** Skills install as real directories in `.agents/skills/{humanize,ai-check}` (canonical source of truth), symlinked into `.claude/skills/` and `.opencode/skills/` — identical to the 20+ existing skills
- **D-02:** Gate policy is exactly ONE ai-check and at most TWO humanize passes; never re-run ai-check after the second pass
- **D-03:** Gate lives in the command docs (new Phase E.5 in `viral-script.md`) — no code changes; the LLM enforces it while executing the command
- **D-04:** Publish metadata gate added to both `publish-video.md` variants (`.agents/commands/` and `.agents/commands.claude/`)
- **D-05:** Voice matching uses `channels/{name}/voice/` folder convention (`.txt`/`.md` samples) — no new config field needed
- **D-06:** Missing skills must be surfaced, never silently skipped — added to `doctor.py` and `viral-setup.md` dependency checks
- **D-07:** Humanization note persisted in the JSONL `notes` field (e.g. `"humanized:2x, ai-check: Likely Human (6/27)"`)

</decisions>

<canonical_refs>
## Canonical References

### Specification
- `.planning/phases/15-humanization-gate/15-SPEC.md` — Locked requirements, boundaries, acceptance criteria

### Skills
- `.agents/skills/humanize/SKILL.md` — Humanization skill (vendored from github.com/harshaneel/humanize, MIT)
- `.agents/skills/ai-check/SKILL.md` — AI-detection audit skill

### Workflow Documents
- `AGENTS.md` — Stage 3 Script + Stage 5 Publish humanization gates
- `.agents/docs/script.md` — Humanization Gate checkpoint details
- `.agents/docs/publish.md` — Metadata Humanization Gate details
- `.agents/commands.claude/viral-script.md` — Phase E.5 Humanization Gate
- `.agents/commands.claude/publish-video.md` — Metadata gate steps
- `.agents/agents/viral-pipeline.md` — Orchestrator gate enforcement
- `.opencode/opencode.json` — humanize/ai-check allowed for build + viral-pipeline agents

### Related
- `.planning/ROADMAP.md` § Phase 15 — Humanization Gate
- `.planning/REQUIREMENTS.md` § Content Humanization (HUMANIZE-01..05)

</canonical_refs>

---

*Phase: 15-humanization-gate*
*Context gathered: 2026-08-14*