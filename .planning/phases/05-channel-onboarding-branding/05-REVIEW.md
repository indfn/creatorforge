---
phase: 05-channel-onboarding-branding
reviewed: 2026-07-14T10:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - agent_core/publishing/oauth.py
  - scripts/setup-yt-oauth.py
  - scripts/setup-channel-branding.py
  - schemas/channel-config.schema.json
  - .agents/commands/viral-onboard.md
  - .planning/phases/05-channel-onboarding-branding/05-CONTEXT.md
findings:
  critical: 3
  warning: 6
  info: 6
  total: 15
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-07-14T10:00:00Z
**Depth:** Standard
**Files Reviewed:** 6
**Status:** Issues Found

## Summary

Reviewed 6 files covering Phase 5 (Channel Onboarding & Branding) — the OAuth core module (`oauth.py`), OAuth setup script (`setup-yt-oauth.py`), channel branding script (`setup-channel-branding.py`), the JSON schema (`channel-config.schema.json`), the agent onboarding command (`viral-onboard.md`), and the phase context document.

The phase has solid architectural decisions documented in CONTEXT.md (per-channel tokens, manual-only avatar, auto-refresh), but the implementation has three critical issues: the OAuth setup script lacks the `youtube` scope required for channel management API calls, does not support the `--channel` argument referenced by the agent command, and has two `type=bool` argparse flags that treat `"false"` as `True`. Additionally, API error handling is absent around all YouTube API calls, and the import of `validate_or_raise` is unprotected despite being inconsistent with the guarded `googleapiclient` imports.

## Critical Issues

### CR-01: Missing `youtube` scope — branding API calls will 403

**File:** `scripts/setup-yt-oauth.py:26-29`
**Issue:** The OAuth setup script requests only `yt-analytics.readonly` and `youtube.readonly` scopes. Channel management API calls (channels.update, channelBanners.insert, watermarks.set) require the `youtube` scope (or at minimum `youtube.force-ssl`). The branding script will receive HTTP 403 Forbidden errors for every API call.

The context document (D-08) correctly notes that the same token will be used for all phases, but the scopes here are too narrow.

**Fix:** Add the `youtube` scope to the SCOPES list:
```python
SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube",        # channel management
    "https://www.googleapis.com/auth/youtube.upload",  # publishing (Phase 6)
]
```

### CR-02: setup-yt-oauth.py has no `--channel` argument — token saved globally, not per-channel

**File:** `scripts/setup-yt-oauth.py:33-35,38`
**Issue:** The agent command in `viral-onboard.md` instructs: `python scripts/setup-yt-oauth.py --channel {name}`. However, the script defines no `--channel` argument. It saves the token to a global path `~/.viral-command/yt-token.json` instead of the per-channel path `channels/{Name}/yt-oauth-token.json` as required by D-10. This means:
1. All channels share one token
2. The path `~/.viral-command` is stale (old project name)
3. The `oauth_token_path` field in `channel_config.json` won't match

**Fix:** Add a `--channel` argument, compute per-channel path, and save there:
```python
parser.add_argument("--channel", required=True, help="Channel name")
args = parser.parse_args()
TOKEN_DIR = PROJECT_ROOT / "channels" / args.channel
TOKEN_PATH = TOKEN_DIR / "yt-oauth-token.json"
```

### CR-03: `type=bool` argparse flags treat `"false"` as `True`

**File:** `scripts/setup-channel-branding.py:60-61`
**Issue:** Lines 60-61 use `type=bool` for `--allow-embed` and `--allow-comments`. In Python argparse, `type=bool` passes the string argument through `bool()`, and `bool("false")` is `True` because it's a non-empty string. Every possible CLI value except an empty string evaluates to `True`:

| Input | Actual | Expected |
|-------|--------|----------|
| `--allow-embed true` | `True` | `True` |
| `--allow-embed false` | `True` | `False` |
| `--allow-embed True` | `True` | `True` |
| `--allow-embed False` | `True` | `False` |

**Fix:** Use `action="store_true"` / `action="store_false"` or a proper boolean parser:
```python
parser.add_argument("--allow-embed", action="store_true",
                    default=None, help="Allow embedding by default")
parser.add_argument("--no-allow-embed", action="store_false",
                    dest="allow_embed", help="Disallow embedding by default")
parser.add_argument("--allow-comments", action="store_true",
                    default=None, help="Allow comments by default")
parser.add_argument("--no-allow-comments", action="store_false",
                    dest="allow_comments", help="Disallow comments by default")
```
Then replace `if args.allow_embed is not None:` with similar logic.

Alternatively, use a custom type converter:
```python
def str_to_bool(v: str) -> bool:
    if v.lower() in ("true", "1", "yes"): return True
    if v.lower() in ("false", "0", "no"): return False
    raise argparse.ArgumentTypeError(f"Boolean value expected: {v}")
```

## Warnings

### WR-01: No API error handling — all YouTube API calls can crash the script

**File:** `scripts/setup-channel-branding.py:68-70,114-115,130-145,155-166**
**Issue:** None of the YouTube API calls (`channels().list().execute()`, `channels().update().execute()`, `channelBanners().insert().execute()`, `watermarks().set().execute()`) are wrapped in try/except blocks. Any `googleapiclient.errors.HttpError` (rate limiting, quota exhaustion, auth failure, invalid arguments) will crash the entire script mid-way, potentially after partial work has been done (e.g., banner uploaded but not applied to channel).

The context document D-12 states: "No silent failures — all API errors surface with HTTP status and context," but there is zero error handling.

**Fix:** Wrap each API call with error handling:
```python
from googleapiclient.errors import HttpError

try:
    channels_response = youtube.channels().list(
        part="brandingSettings,id", mine=True
    ).execute()
except HttpError as e:
    print(f"  ERROR: YouTube API request failed (HTTP {e.status_code}): {e.reason}")
    print(f"  Try: python scripts/setup-yt-oauth.py --channel {args.channel}")
    sys.exit(1)
```

### WR-02: Banner mimetype hardcoded to `image/jpeg`

**File:** `scripts/setup-channel-branding.py:130`
**Issue:** `MediaFileUpload` is created with `mimetype="image/jpeg"` regardless of the actual file type. If the user provides a PNG banner (YouTube banners are often exported as PNG), the API may reject it or the upload may silently misinterpret the content type.

**Fix:** Infer mimetype from file extension or use `mimetype=None` to let the library guess:
```python
from mimetypes import guess_type
mime = guess_type(str(banner_path))[0] or "image/jpeg"
media = MediaFileUpload(str(banner_path), mimetype=mime, resumable=True)
```

### WR-03: Missing/partial channel config leads to confusing schema validation failure

**File:** `scripts/setup-channel-branding.py:33-37,210-215**
**Issue:** If `channel_config.json` doesn't exist, `get_channel_config()` returns `{}`. The script later populates only `config["branding"]` and `config["defaults"]` but never creates the required top-level keys `brand`, `youtube`, `production`. Schema validation then fails with a generic error like "`brand` is a required property" — the user gets no guidance about what's missing or why.

**Fix:** Check for missing required fields and provide a clear message:
```python
config = get_channel_config(args.channel)
required_top = ["channel_name", "brand", "youtube", "production"]
missing = [k for k in required_top if k not in config]
if missing:
    print(f"  ERROR: channel_config.json is missing required fields: {', '.join(missing)}")
    print(f"  Run the channel onboarding command to create a valid config first.")
    sys.exit(1)
```

### WR-04: `channel_id` stored in `branding` but not in `youtube` section

**File:** `scripts/setup-channel-branding.py:196`
**Issue:** The script writes `channel_id` only to `config["branding"]["channel_id"]` but never to `config["youtube"]["channel_id"]`. The schema defines `channel_id` in both `youtube` (line 24) and `branding` (line 78). Other components (Phase 6 publishing, Phase 7 analytics) will likely read from the `youtube` object. Writing only to `branding` creates a brittle split where the canonical channel ID location depends on which script last wrote it.

**Fix:** Write `channel_id` to both locations:
```python
config.setdefault("youtube", {})
config["branding"]["channel_id"] = channel_id
config["youtube"]["channel_id"] = channel_id
```

### WR-05: `sys.path.insert(0, ...)` violates completed SEC-06

**File:** `scripts/setup-channel-branding.py:30`
**Issue:** REQUIREMENTS.md marks SEC-06 ("Replace all `sys.path.insert(0, ...)` with proper package imports") as completed (`[x]`). However, this script still uses `sys.path.insert(0, str(PROJECT_ROOT))` on line 30. This is either:
- A regression (new code reintroducing a fixed pattern)
- Or SEC-06 was prematurely marked complete

**Fix:** Remove the `sys.path.insert` and ensure the project is installed in development mode (`pip install -e .`) or add proper `PYTHONPATH` management in a shebang wrapper.

### WR-06: Unprotected import of `validate_or_raise` with inconsistent error handling

**File:** `scripts/setup-channel-branding.py:18-26**
**Issue:** The `googleapiclient` imports (lines 19-24) are wrapped in try/except with a user-friendly "Missing dependency" message and `sys.exit(1)`. But the `validate_or_raise` import on line 26 is NOT wrapped in any try/except. If `jsonschema` (a transitive dependency of `validation.py`) is missing, the script crashes with a bare traceback:

```
ModuleNotFoundError: No module named 'jsonschema'
```

Additionally, `requirements.txt` does not list `jsonschema` (though `pyproject.toml` does), making this more likely when installed via `pip install -r requirements.txt`.

**Fix:** Wrap the import consistently:
```python
try:
    from agent_core.core.validation import validate_or_raise
except ImportError:
    print("Missing dependency: pip install jsonschema")
    sys.exit(1)
```

## Info

### IN-01: oauth.py stubs not yet implemented

**File:** `agent_core/publishing/oauth.py:10-31`
**Issue:** Both `get_authenticated_service()` and `refresh_token_if_expired()` are stubs raising `NotImplementedError`. This is expected for a phase that hasn't implemented the core module yet (D-01 defers to this phase). Worth noting because `setup-channel-branding.py` imports `get_authenticated_service` on line 21 and would crash when calling it. The function signature also lacks `service_name` and `version` parameters — Phase 7 will need Analytics API (`youtubeAnalytics` service), which differs from the Data API (`youtube` service).

**Suggestion:** When implementing, add optional parameters:
```python
def get_authenticated_service(
    channel: str,
    service_name: str = "youtube",
    version: str = "v3",
) -> googleapiclient.discovery.Resource:
```

### IN-02: Unused `import os` in setup-yt-oauth.py

**File:** `scripts/setup-yt-oauth.py:16`
**Issue:** `import os` is imported but never referenced anywhere in the script. Dead import.

**Fix:** Remove the line.

### IN-03: Hardcoded watermark timing parameters

**File:** `scripts/setup-channel-branding.py:160-164**
**Issue:** Watermark offset (5000ms) and duration (15000ms) are hardcoded. For very short videos (<20s), the watermark may never appear or may be cut off. These could be CLI arguments with sensible defaults.

**Suggestion:** Add optional `--watermark-offset-ms` and `--watermark-duration-ms` arguments:
```python
parser.add_argument("--watermark-offset-ms", type=int, default=5000,
                    help="Watermark appear offset in ms (default: 5000)")
parser.add_argument("--watermark-duration-ms", type=int, default=15000,
                    help="Watermark display duration in ms (default: 15000)")
```

### IN-04: `channel_id` defined in two schema locations

**File:** `schemas/channel-config.schema.json:24,78`
**Issue:** The schema defines `channel_id` under both `youtube` (line 24) and `branding` (line 78). This creates ambiguity about which is canonical. The branding script writes to `branding.channel_id` but never to `youtube.channel_id`.

**Suggestion:** Remove one of the two definitions. `youtube.channel_id` is the semantically correct location since the channel ID is a YouTube platform identifier, not a branding attribute.

### IN-05: Inconsistent indentation in viral-onboard.md list

**File:** `.agents/commands/viral-onboard.md:11`
**Issue:** Line 11 is indented with 6 extra spaces relative to line 10, making it render as a sub-list item in some markdown renderers rather than a sibling list item. This doesn't affect agent readability but is a minor formatting inconsistency.

### IN-06: No test files for Phase 5 modules

**File:** (project-wide)
**Issue:** No test files exist for `oauth.py` or the branding scripts. `glob` searches for `test_*oauth*` and `test_*channel*` returned no results. Testing OAuth token refresh, error handling paths, and schema validation is important given the complexity of the YouTube API interactions.

**Suggestion:** Add tests:
- `tests/test_oauth.py`: Mock `google_auth_oauthlib` and verify token load/refresh/save
- `tests/test_setup_channel_branding.py`: Mock API responses and verify partial updates

---

_Reviewed: 2026-07-14T10:00:00Z_
_Reviewer: gsd-code-reviewer (agent)_
_Depth: standard_
