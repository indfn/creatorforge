---
description: Set up a new channel profile (ICP, pillars, competitors) and brand it on YouTube
---
@.agents/commands.claude/viral-onboard.md

Arguments: $ARGUMENTS

IMPORTANT:
  1. Prompt for the channel name, then create channels/{name}/brain.json and channels/{name}/channel_config.json
  2. After creating the local profile, guide the user through YouTube OAuth + branding:
     - python scripts/setup-yt-oauth.py --channel {name}
     - python scripts/setup-channel-branding.py --channel {name} --description "..." --keywords "tag1,tag2" [--default-privacy private|unlisted|public] [--default-license youtube|creativeCommon] [--allow-embed true|false] [--allow-comments true|false]
  3. If branding assets (banner, watermark) aren't available yet, skip them — channel text setup is sufficient for Phase 5
  4. Channel must exist on YouTube first (created manually by the user)
  5. Avatar/profile picture must be uploaded manually:
     - YouTube Data API v3 has no channel avatar endpoint
     - Ask the user to upload at YouTube Studio → Customization → Branding
     - Reference: `scripts/setup-channel-branding.py --channel {name} --avatar path/to/avatar.jpg`
     - The --avatar flag only stores the path — no API call is made
