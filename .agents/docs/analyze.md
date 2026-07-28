# Analyze

## Purpose

Collect performance data from published videos — basic metrics at 24h, deep behavioral metrics (CTR, AVD, retention) at 72h+.

## Input Contract

- Published video ID from `brain.json` (set after publish)
- Channel OAuth tokens with YouTube Analytics API scope
- Minimum 24h since publish for basic data, 72h for deep data

## Commands

```bash
viral-analyze --channel {name}
```

Optional:
- `--video-id <id>` — single-video analysis

## Output Artifacts

- Analytics entries persisted to `channels/{name}/data/analytics/` as schema-validated JSONL
- Insights aggregated in analytics module

## Error Recovery

- Verify video age meets collection thresholds (24h basic / 72h deep)
- Check OAuth token has Analytics API scope
- Confirm YouTube Analytics API quota available

## Manual Only Ops

None.

## Related

- [AGENTS.md](../AGENTS.md) — Pipeline overview
- [.agents/commands/viral-analyze.md](../commands/viral-analyze.md) — Command reference
