# Script

## Purpose

Generate a full video script from the selected angle, split into scenes with hooks, narrative flow, and visual cues.

## Input Contract

- Selected angle from Stage 2 in `brain.json`
- Channel config for tone/style preferences

## Commands

```bash
viral-script --channel {name} [--angle-id <id>]
```

Uses the specified angle or latest available.

## Output Artifacts

- Per-scene script files at `channels/{name}/active_production/scene_*_script.txt`
- Master script JSON at `channels/{name}/active_production/script.json`

## Error Recovery

- Verify LLM API key is set
- Check `active_production/` directory exists (create if missing)
- Ensure angle data is present in `brain.json`

## Manual Only Ops

None.

## Related

- [AGENTS.md](../AGENTS.md) — Pipeline overview
- [.agents/commands/viral-script.md](../commands/viral-script.md) — Command reference
