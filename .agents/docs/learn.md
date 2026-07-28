# Learn

## Purpose

Evolve brain learning weights from real performance data to improve future content strategy.

## Input Contract

- Analytics data from Stage 6 (minimum 3 videos per content pillar)
- Existing `brain.json` with current weights

## Commands

```bash
viral-update-brain --channel {name}
```

Optional:
- `--force` — bypass the 3-video minimum threshold

## Output Artifacts

- `channels/{name}/brain.json` updated with refined weights
- Weight changes logged for review

## Error Recovery

- Not enough data yet — continue publishing until at least 3 videos per pillar exist
- Verify analytics data is present and complete
- Brain weights require variance in performance data to produce meaningful updates

## Manual Only Ops

None.

## Related

- [AGENTS.md](../AGENTS.md) — Pipeline overview
- [.agents/commands/viral-update-brain.md](../commands/viral-update-brain.md) — Command reference
