# Angle

## Purpose

Develop content angles from discovered topics using channel-specific brain weights to prioritize winning formulations.

## Input Contract

- Channel `brain.json` with discovered topics from Stage 1

## Commands

```bash
viral-angle --channel {name}
```

Optional:
- `--topic "..."` — skip selection and angle a specific topic directly

## Output Artifacts

- Content angles with hook concepts stored in `channels/{name}/brain.json`

## Error Recovery

- Ensure discover stage completed and `brain.json` has topics
- Verify LLM API key is available

## Manual Only Ops

None.

## Related

- [AGENTS.md](../AGENTS.md) — Pipeline overview
- [.agents/commands/viral-angle.md](../commands/viral-angle.md) — Command reference
