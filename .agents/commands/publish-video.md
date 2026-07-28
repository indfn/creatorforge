---
description: Upload rendered video to linked YouTube channel with peak-time scheduling
---
Arguments: $ARGUMENTS

Read the active channel from channels/$(cat .channel-active 2>/dev/null || echo "ChannelA")/.

1. Verify render output exists: channels/{name}/active_production/render/final_video.mp4
2. Load channel_config.json for YouTube channel ID and OAuth token path
3. Calculate optimal publish time via: python3 -c "from agent_core.publishing.scheduler import best_time; print(best_time('$(cat .channel-active)'))"
4. Upload: python3 -m agent_core.publishing.uploader --channel {name} [--schedule HH:MM]
5. Update brain.json metadata with publish timestamp
6. Report upload status and public URL
