# Phase 5: Channel Onboarding & Branding - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning

<domain>
## Phase Boundary

New YouTube channels can be fully set up through the agent — linked via OAuth, branded with description/tags/avatar/banner/watermark, and pre-configured with default upload settings — so the channel is ready to receive content before the first publish.

**Prerequisite:** Channel must exist on YouTube (created manually by user — API cannot create channels).

</domain>

<decisions>
## Implementation Decisions

### Architecture: Core module + thin CLI wrappers
- **D-01:** OAuth token lifecycle logic lives in `agent_core/publishing/oauth.py` — implement `get_authenticated_service()` and `refresh_token_if_expired()`
- **D-02:** `scripts/setup-yt-oauth.py` becomes a thin CLI wrapper calling the core module
- **D-03:** `scripts/setup-channel-branding.py` uses `get_authenticated_service()` instead of re-building Credentials inline
- **D-04:** `agent_core/publishing/oauth.py` is the single OAuth entry point for all phases (Phase 5, 6, 7)

### CHANNEL-03: Avatar upload — manual-only
- **D-05:** YouTube Data API v3 has NO endpoint for channel profile picture (avatar) — mark CHANNEL-03 as manual-only
- **D-06:** `channel_config.json` can store a `avatar_path` reference for documentation, but no API call is attempted
- **D-07:** Document the limitation in the agent onboarding command (viral-onboard.md) and REQUIREMENTS.md

### Token lifecycle: Seamless auto-refresh
- **D-08:** `get_authenticated_service()` loads token → builds `Credentials` with refresh_token/client_id/client_secret → passes to `youtube.build()` — google-api-python-client auto-refreshes on 401
- **D-09:** No separate scheduled refresh step needed — refresh is transparent on each API call
- **D-10:** Token persisted per-channel at `channels/{Name}/yt-oauth-token.json`

### Error recovery: Clear messages with actionable prompts
- **D-11:** Every error message includes the exact next command the user should run
- **D-12:** No silent failures — all API errors surface with HTTP status and context
- **D-13:** Avatar/banner upload skipped gracefully (warning, not error) when file path is missing

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements
- `.planning/REQUIREMENTS.md` — CHANNEL-01 through CHANNEL-07 requirements and acceptance criteria
- `.planning/ROADMAP.md` — Phase 5 goal, success criteria, and dependencies

### Existing Implementation
- `scripts/setup-yt-oauth.py` — OAuth CLI flow (to be refactored)
- `scripts/setup-channel-branding.py` — Channel branding CLI (to be refactored)
- `agent_core/publishing/oauth.py` — OAuth stubs (to be implemented)
- `channels/ChannelA/channel_config.json` — Reference channel config shape
- `schemas/channel-config.schema.json` — Schema definition
- `.agents/commands/viral-onboard.md` — Agent onboarding command (update with manual avatar note)

### Architecture References
- `.planning/codebase/ARCHITECTURE.md` — Agent_core module layout
- `.planning/codebase/INTEGRATIONS.md` — YouTube OAuth integration details
- `.planning/codebase/CONVENTIONS.md` — Code style, JSON schema patterns
- `.planning/codebase/STRUCTURE.md` — Directory layout

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent_core/publishing/oauth.py` — Existing stubs for `get_authenticated_service()` and `refresh_token_if_expired()`
- `google-auth-oauthlib` + `google-api-python-client` — Already in project dependencies (imported in scripts)
- `channels/ChannelA/channel_config.json` — Pattern for per-channel config structure
- `schemas/channel-config.schema.json` — JSON Schema for config validation

### Established Patterns
- CLI scripts in `scripts/` use `argparse` with `--channel` required flag
- Channel config loaded/saved via `json.loads`/`json.dumps` with `channel_config.json`
- Token stored as JSON with token, refresh_token, client_id, client_secret, token_uri, scopes

### Integration Points
- `agent_core/publishing/oauth.py` — Single module that Phase 6 (publishing) and Phase 7 (analytics) both depend on
- `channels/{Name}/channel_config.json` — `youtube.oauth_token_path` field references token location

</code_context>

<specifics>
- OAuth SCOPES needed: `youtube` (channel management), `youtube.upload` (publishing), `yt-analytics.readonly` (analytics) — all set in current scripts, keep as-is
- Dual-credential architecture: Project B (OAuth for publishing/branding/analytics) vs Project A (API key for scraping) — maintain separation
</specifics>

<deferred>
None — discussion stayed within phase scope.
</deferred>

---

*Phase: 05-channel-onboarding-branding*
*Context gathered: 2026-07-13*
