# Discover

## Purpose

Find winning topics for the active channel through competitor analysis and keyword research.

## Input Contract

- Active channel at `channels/{name}/` with `channel_config.json` and `brain.json`
- API keys for YouTube/Instagram in `.env`
- Groq API key for transcription

## Commands

```bash
viral-discover --channel {name}
```

Optional flags:
- `--platform youtube|instagram` — scope search to one platform
- `--count N` — limit number of results

## Output Artifacts

- Scored topics appended to `channels/{name}/brain.json` under `discovered_topics`
- Checkpoint artifacts in channel state

## Error Recovery

- Run `creatorforge doctor` to verify API key status
- Check YouTube/Instagram quota not exhausted
- Verify network connectivity to API endpoints

## Manual Only Ops

None.

## Related

- [AGENTS.md](../AGENTS.md) — Pipeline overview
- [.agents/commands/viral-discover.md](../commands/viral-discover.md) — Command reference
