# /hyperframes:lint — Pre-render Semantic Checker

**Arguments:** $ARGUMENTS

Run: `python3 production/RenderEngine/linter.py --channel $(cat .channel-active 2>/dev/null || echo "ChannelA")`

Check:
- Visual timestamps align with audio duration from `aligned_transcript.json`
- All referenced assets exist under `active_production/assets/`
- Script JSON is valid against `schemas/production-order.schema.json`
- Render directory has enough context for assembly
