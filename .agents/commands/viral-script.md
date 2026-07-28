---
description: Generate hook and master JSON script from an angle for the active channel
---
@.agents/commands.claude/viral-script.md

Arguments: $ARGUMENTS

IMPORTANT: Read the active channel from channels/$(cat .channel-active 2>/dev/null || echo "ChannelA")/ and use that channel's brain.json. Output scripts to channels/{name}/active_production/.
