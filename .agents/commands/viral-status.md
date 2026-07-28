---
description: Show pipeline dashboard for the active channel
---
Show a status dashboard for the active channel including:
- Brain: ICP, pillars, competitor count, last update
- Pipeline: pending topics, active angle, script in progress
- Publishing: scheduled uploads, last publish date
- Analytics: total content analyzed, avg CTR, top format

Read the active channel from channels/$(cat .channel-active 2>/dev/null || echo "ChannelA")/.
Scan all data subdirectories and active_production/ for current state.
