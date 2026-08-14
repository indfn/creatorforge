---
description: Generate hook and master JSON script from an angle for the active channel
---
@.agents/commands.claude/viral-script.md

Arguments: $ARGUMENTS

IMPORTANT: Read the active channel from channels/$(cat .channel-active 2>/dev/null || echo "ChannelA")/ and use that channel's brain.json. Output scripts to channels/{name}/active_production/.

The Humanization Gate (Phase E.5 in the imported spec) is MANDATORY: apply the `humanize` skill during script generation, then run `ai-check` exactly once. If the verdict is Uncertain/Likely AI/AI, run `humanize` once more (max 2 passes). Do NOT re-run ai-check. Voice samples for writer-profile distillation live in channels/{name}/voice/ (create it and add .txt/.md samples to match the creator's voice).
