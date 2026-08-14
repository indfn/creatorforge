# Script

## Purpose

Generate a full video script from the selected angle, split into scenes with hooks, narrative flow, and visual cues.

## Input Contract

- Selected angle from Stage 2 in `brain.json`
- Channel config for tone/style preferences
- Voice samples from `channels/{name}/voice/` (optional — for humanize writer-profile distillation)

## Commands

```bash
viral-script --channel {name} [--angle-id <id>]
```

Uses the specified angle or latest available.

## Humanization Gate (mandatory checkpoint)

Every script output must pass the Humanization Gate before persistence:

1. **Humanize during generation** — apply the `humanize` skill's nine levers (perplexity injection, burstiness, hedge surgery, structural flattening, specificity insertion, voice/register, human transitions, punctuation normalization, RLHF-voice strip) from the first draft of all hooks, talking points, beats, and post copy
2. **Voice matching** — if `channels/{name}/voice/` has `.txt`/`.md` writing samples, distill writer-profile hypotheses (protocol step 0 of `humanize`) and rewrite in the creator's voice
3. **ai-check exactly ONCE** — run the `ai-check` skill for the full report (verdict, score /27, signal breakdown, evidence log). Pass = `Human`/`Likely Human` (≤8)
4. **Second humanize (max ONCE)** — on fail (`Uncertain`/`Likely AI`/`AI`), humanize once more targeting the flagged signals. Do NOT re-run ai-check
5. **Persist** — save with a humanization note in the JSONL `notes` field (e.g. `"humanized:2x, ai-check: Likely Human (6/27)"`)

Policy ceiling: exactly one ai-check, at most two humanize passes.

## Output Artifacts

- Per-scene script files at `channels/{name}/active_production/scene_*_script.txt`
- Master script JSON at `channels/{name}/active_production/script.json`

## Error Recovery

- Verify LLM API key is set
- Check `active_production/` directory exists (create if missing)
- Ensure angle data is present in `brain.json`
- If the Humanization Gate cannot run (missing `humanize`/`ai-check` skills), do NOT skip it silently — surface the missing skill and fall back to applying the levers manually from the SKILL.md text

## Manual Only Ops

None.

## Related

- [AGENTS.md](../AGENTS.md) — Pipeline overview
- [.agents/commands/viral-script.md](../commands/viral-script.md) — Command reference
- [.agents/skills/humanize/SKILL.md](../skills/humanize/SKILL.md) — Humanization skill
- [.agents/skills/ai-check/SKILL.md](../skills/ai-check/SKILL.md) — AI-detection audit skill
