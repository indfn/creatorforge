# Plan 15-01: Install Skills + Wire Humanization Gate

**Phase:** 15-humanization-gate
**Plan:** 01
**Status:** Complete
**Files modified:** 13 + 6 new

## What was done

Integrated the `humanize` and `ai-check` skills (from github.com/harshaneel/humanize, MIT) into the CreatorForge workflow as a mandatory Humanization Gate on the Script and Publish stages.

## Output

**Skills (canonical + symlinks):**
- `.agents/skills/humanize/` — SKILL.md + references/research.md + LICENSE (MIT attribution)
- `.agents/skills/ai-check/` — SKILL.md + LICENSE
- Symlinks: `.claude/skills/{humanize,ai-check}`, `.opencode/skills/{humanize,ai-check}` → `.agents/skills/`

**Command docs (enforcement):**
- `.agents/commands.claude/viral-script.md` — new Phase E.5 Humanization Gate (1 ai-check, max 2 humanize passes, no re-check); wired into longform confirm, shortform confirm, both LinkedIn save paths, both persist phases, and Important Rules
- `.agents/commands/viral-script.md` — gate mandate + voice-sample note in wrapper
- `.agents/commands.claude/publish-video.md` + `.agents/commands/publish-video.md` — metadata humanization step before upload
- `.agents/commands.claude/viral-setup.md` — Steps 4b/4c: humanize/ai-check skill + voice sample dependency checks

**Workflow docs:**
- `AGENTS.md` — Stage 3 Script + Stage 5 Publish gates, recovery guidance
- `.agents/docs/script.md` — Humanization Gate checkpoint section
- `.agents/docs/publish.md` — Metadata Humanization Gate section
- `.agents/agents/viral-pipeline.md` — orchestrator gate enforcement note
- `.opencode/opencode.json` — humanize/ai-check allowed for build + viral-pipeline agents

**Voice matching:**
- `channels/ChannelA/voice/README.md` — convention + how it's used
- `scripts/init-creatorforge.sh` — scaffolds `voice/` for new channels

**Tooling:**
- `scripts/doctor.py` — `Humanize skills installed` + per-channel `Voice samples` checks

## Acceptance criteria met

- [x] Skills installed canonically in `.agents/skills/` with LICENSE, symlinked into both agent folders
- [x] Script gate: humanize during generation → ai-check exactly once → max 2 humanize passes → no re-check
- [x] Publish metadata gate in both command variants
- [x] Voice samples convention wired (ChannelA dir, init scaffold, doctor + setup checks)
- [x] Enforcement across AGENTS.md, per-stage docs, commands, agent prompt, opencode.json
- [x] All 734 tests pass; opencode.json valid JSON

## Requirement satisfied

HUMANIZE-01, HUMANIZE-02, HUMANIZE-03, HUMANIZE-04, HUMANIZE-05