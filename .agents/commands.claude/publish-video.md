# /viral:publish — YouTube Upload & Schedule

**Arguments:** $ARGUMENTS

Read the active channel from `channels/$(cat .channel-active 2>/dev/null || echo "ChannelA")/`.

1. Verify render output exists: `channels/{name}/active_production/render/final_video.mp4`
2. Load `channel_config.json` for YouTube channel ID and OAuth token path
3. Calculate optimal publish time via: `python3 -c "from agent_core.publishing.scheduler import best_time; print(best_time('$(cat .channel-active)'))"`
4. Humanize metadata: run the `humanize` skill on the generated title, description, and CTA text (from `active_production/script.json` via `agent_core.publishing.metadata`). Run `ai-check` **once** on the assembled description. If the verdict is `Uncertain`/`Likely AI`/`AI`, run `humanize` once more (max 2 passes) — do NOT re-run ai-check. If voice samples exist in `channels/{name}/voice/`, use them for writer-profile distillation.
5. Upload: `python3 -m agent_core.publishing.uploader --channel {name} [--schedule HH:MM]` (pass the finalized humanized title/description via `--title`/`--description` if the uploader supports overrides, or let metadata.py generate from the humanized script)
6. Update `brain.json` metadata with publish timestamp
7. Report upload status and public URL
