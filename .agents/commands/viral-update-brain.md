---
description: Evolve agent brain from performance data for the active channel
---
@.agents/commands.claude/viral-update-brain.md

Arguments: $ARGUMENTS

IMPORTANT: Read the active channel from channels/$(cat .channel-active 2>/dev/null || echo "ChannelA")/ and use that channel's brain.json. All data reads/writes go to channels/{name}/data/.
