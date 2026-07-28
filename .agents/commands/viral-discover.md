---
description: Multi-Platform Topic Discovery — competitor analysis + keyword search scoped to active channel
---
Here is the full command specification for viral discovery:

@.agents/commands.claude/viral-discover.md

Arguments: $ARGUMENTS

IMPORTANT: Read the active channel from channels/$(cat .channel-active 2>/dev/null || echo "ChannelA")/ and use that channel's brain.json instead of data/agent-brain.json. All data reads/writes go to channels/{name}/data/.
