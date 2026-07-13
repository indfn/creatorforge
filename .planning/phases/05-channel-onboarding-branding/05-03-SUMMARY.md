# Plan 05-03 Summary: Default Settings & Integration

**Status:** READY_FOR_EXECUTION
**Requirements:** CHANNEL-06, CHANNEL-07
**Wave:** 3
**Depends on:** 05-02

## Objective

Add schema validation to the channel branding save flow and update the channel config schema to include `branding` and `defaults` fields, completing the persistence integration for CHANNEL-06 and CHANNEL-07.

## Tasks

| # | Name | Files | Type |
|---|------|-------|------|
| 1 | Update channel-config.schema.json with branding and defaults fields | `schemas/channel-config.schema.json` | auto |
| 2 | Add schema validation to setup-channel-branding.py before save | `scripts/setup-channel-branding.py` | auto |
| 3 | Update viral-onboard.md with manual avatar note and refactored CLI usage | `.agents/commands/viral-onboard.md` | auto |

## Key Design Decisions

- **Schema fields are optional** — `branding` and `defaults` are not in the `required` array because they're populated by the branding script and may not exist in initial configs
- **Validation before save** — `validate_or_raise` is called before `save_channel_config()` to prevent writing invalid configs (per existing pattern in `agent_core/core/checkpoint.py` and `agent_core/core/quota.py`)
- **No API endpoint for default upload settings** — YouTube API has no channel-level endpoint for default upload settings. These are tracked locally in `channel_config.json["defaults"]` and consumed by Phase 6 (publishing) during upload
- **Avatar limitation documented** — per D-05/D-07, the manual avatar limitation is documented in viral-onboard.md since YouTube API has no avatar upload endpoint
</success_criteria>
