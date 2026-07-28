# /hyperframes:render — Assemble & Pre-render

**Arguments:** $ARGUMENTS

Read the active channel from `channels/$(cat .channel-active 2>/dev/null || echo "ChannelA")/`.

1. Load `active_script.json` from `channels/{name}/active_production/`
2. Load `aligned_transcript.json` if available
3. Load `channel_config.json` for visual identity (colors, fonts)
4. Assemble hyperframe HTML blueprint into `channels/{name}/active_production/render/index.html`
5. Run linter: `python3 production/RenderEngine/linter.py --channel {name}`
6. Report any lint warnings or PASS status
