# Phase 15: Humanization Gate — SPEC

**Locked:** 2026-08-14
**Status:** Complete

## Requirements

### HUMANIZE-01: Skills installed canonically
`humanize` and `ai-check` exist as real directories in `.agents/skills/` with upstream MIT license attribution (LICENSE files). Symlinks present in `.claude/skills/` and `.opencode/skills/` following the existing per-skill symlink pattern.

### HUMANIZE-02: Script-stage Humanization Gate
`viral-script` applies the `humanize` skill during script generation, then runs `ai-check` **exactly once**. If the verdict is `Uncertain`/`Likely AI`/`AI`, run `humanize` **once more** (max 2 passes). Never re-run ai-check. No script persists without passing the gate. Humanization note appended to the persisted JSONL `notes` field.

### HUMANIZE-03: Publish-stage Metadata Humanization Gate
`publish-video` runs `humanize` on the generated title, description, and CTA text, then `ai-check` once before upload. Same max-2-pass / no-recheck policy.

### HUMANIZE-04: Voice matching
`channels/{name}/voice/` holds `.txt`/`.md` writing samples for humanize writer-profile distillation. Created for ChannelA (with README), scaffolded by `init-creatorforge.sh`, and checked by `creatorforge doctor` and `viral-setup`.

### HUMANIZE-05: Workflow enforcement
The gate is documented and enforced across: `AGENTS.md` (Stage 3 + 5), `.agents/docs/script.md`, `.agents/docs/publish.md`, `viral-script.md` (Phase E.5), `publish-video.md`, viral-pipeline agent prompt, `opencode.json` skill permissions, `scripts/doctor.py`, and `viral-setup.md`. Missing skills are surfaced, never silently skipped.

## Acceptance Criteria

- [x] `ls .agents/skills/humanize/SKILL.md .agents/skills/ai-check/SKILL.md` succeeds; LICENSE present in both
- [x] `.claude/skills/humanize`, `.claude/skills/ai-check`, `.opencode/skills/humanize`, `.opencode/skills/ai-check` resolve to `.agents/skills/`
- [x] `viral-script.md` contains a Phase E.5 Humanization Gate with the 1-check/2-pass/no-recheck policy
- [x] Both LinkedIn save paths and both script persist paths reference the gate
- [x] Both `publish-video.md` variants contain the metadata humanization step
- [x] `channels/ChannelA/voice/` exists with README; `init-creatorforge.sh` scaffolds `voice/` for new channels
- [x] `doctor.py` reports `Humanize skills installed` and `Voice samples ({channel})`
- [x] `opencode.json` allows `humanize` and `ai-check` for build + viral-pipeline agents
- [x] All 734 tests pass; `opencode.json` validates as JSON

## Out of Scope

- New pipeline stages or pipeline Python code changes
- Modifying the vendored humanize/ai-check skill content
- Re-architecting the `.claude/` / `.opencode/` symlink layout
- Voice samples content itself (user-provided)

---

*Phase: 15-humanization-gate*
*SPEC locked: 2026-08-14*