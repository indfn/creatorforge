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
