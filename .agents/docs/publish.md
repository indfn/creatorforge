# Publish

## Purpose

Upload rendered video to YouTube with SEO metadata, thumbnail, scheduling, and playlist assignment.

## Input Contract

- Rendered video at `channels/{name}/active_production/render/final_video.mp4` (16:9 variant)
- `channel_config.json` with YouTube channel ID and OAuth tokens
- Optimal publish time calculated via scheduler

## Commands

```bash
publish-video --channel {name} [--schedule HH:MM]
```

Optional:
- `--privacy public|private|unlisted`
- `--thumbnail path/to/image.png` to override keyframe auto-extraction

## Metadata Humanization Gate

The YouTube title, description, and CTA metadata must pass the same humanization policy as the script before upload:

1. Apply the `humanize` skill to the generated title, description, and CTA text
2. Run `ai-check` exactly once on the assembled description
3. On fail (`Uncertain`/`Likely AI`/`AI`), run `humanize` once more (max 2 passes) — do NOT re-run ai-check
4. Use `channels/{name}/voice/` samples for writer-profile distillation if present
5. Upload with the finalized humanized metadata

## Output Artifacts

- Published YouTube video
- `channels/{name}/brain.json` updated with video ID and publish timestamp
- Thumbnail set via `thumbnails.set`

## Error Recovery

- Verify render output exists
- Check OAuth token validity and refresh if expired
- Confirm YouTube upload quota available (QuotaBudget tracks daily)
- Check `channel_config.json` for required channel ID

## Manual Only Ops

- **End screens & Cards:** YouTube Studio → Content → video → Editor. Not available via YouTube Data API. Add after publishing.
- **Thumbnail A/B Testing:** YouTube Studio → Content → Test & Compare. API supports thumbnail upload but not A/B experiments.
- **Community Posts:** YouTube Studio → Community tab. No API for community posts.

## Related

- [AGENTS.md](../AGENTS.md) — Pipeline overview
- [.agents/commands/publish-video.md](../commands/publish-video.md) — Command reference
- [.agents/skills/humanize/SKILL.md](../skills/humanize/SKILL.md) — Humanization skill
- [.agents/skills/ai-check/SKILL.md](../skills/ai-check/SKILL.md) — AI-detection audit skill
