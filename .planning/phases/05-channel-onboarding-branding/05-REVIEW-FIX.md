---
phase: 05-channel-onboarding-branding
fixed_at: 2026-07-14T12:00:00Z
review_path: .planning/phases/05-channel-onboarding-branding/05-REVIEW.md
iteration: 1
findings_in_scope: 9
fixed: 9
skipped: 0
status: all_fixed
---

# Phase 05: Code Review Fix Report

**Fixed at:** 2026-07-14T12:00:00Z
**Source review:** .planning/phases/05-channel-onboarding-branding/05-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 9 (3 critical, 6 warnings)
- Fixed: 9
- Skipped: 0

## Fixed Issues

### CR-01: Missing `youtube` scope — branding API calls will 403

**Files modified:** `scripts/setup-yt-oauth.py`
**Commit:** `d8027b8`
**Applied fix:** Replaced the `youtube.readonly` scope with `youtube` (channel management) and `youtube.upload` (publishing) scopes in `SCOPES`. The `yt-analytics.readonly` scope is retained.

### CR-02: setup-yt-oauth.py has no `--channel` argument — token saved globally

**Files modified:** `scripts/setup-yt-oauth.py`
**Commit:** `ded2a8b`
**Applied fix:** Added `argparse` with a `--channel` (required) argument. Moved `TOKEN_DIR` and `TOKEN_PATH` from module-level constants into `main()`, computed as `PROJECT_ROOT / "channels" / args.channel / "yt-oauth-token.json"`. Also removed unused `import os` (resolves IN-02 incidentally). Updated docstring and usage example.

### CR-03: `type=bool` argparse flags treat `"false"` as `True`

**Files modified:** `scripts/setup-channel-branding.py`
**Commit:** `b60a41a`
**Applied fix:** Changed `--allow-embed` and `--allow-comments` from `type=bool` to `action=argparse.BooleanOptionalAction` with `default=None`. This creates `--allow-embed`/`--no-allow-embed` and `--allow-comments`/`--no-allow-comments` flag pairs. The downstream `if args.allow_embed is not None:` checks continue to work correctly.

### WR-01: No API error handling — all YouTube API calls can crash the script

**Files modified:** `scripts/setup-channel-branding.py`
**Commit:** `0150207`
**Applied fix:** Added `from googleapiclient.errors import HttpError` to the guarded import block. Wrapped all 5 YouTube API calls in `try/except HttpError` blocks:
- `channels().list()` — prints error and suggests re-running OAuth setup, exits
- `channels().update()` (branding settings) — prints error, continues
- `channelBanners().insert()` — prints error, skips banner application
- `channels().update()` (banner apply) — prints error, continues
- `watermarks().set()` — prints error, continues

### WR-02: Banner mimetype hardcoded to `image/jpeg`

**Files modified:** `scripts/setup-channel-branding.py`
**Commit:** `0f1bbb7`
**Applied fix:** Added `import mimetypes`. Changed banner `MediaFileUpload` to use `mimetypes.guess_type(str(banner_path))[0] or "image/jpeg"` to infer the correct MIME type from the file extension.

### WR-03: Missing/partial channel config leads to confusing schema validation failure

**Files modified:** `scripts/setup-channel-branding.py`
**Commit:** `92f136e`
**Applied fix:** After loading config, populate required top-level keys with safe defaults before sections populate: `channel_name`, `brand`, `youtube`, `production`. The `branding` section is also set as default. This prevents schema validation from failing with confusing "required property" errors when no config file exists yet.

### WR-04: `channel_id` stored in `branding` but not in `youtube` section

**Files modified:** `scripts/setup-channel-branding.py`
**Commit:** `cad320e`
**Applied fix:** After writing `channel_id` to `config["branding"]["channel_id"]`, also write it to `config.setdefault("youtube", {})["channel_id"] = channel_id`. The youtube section is guaranteed to exist from the WR-03 fix, and the defensive `setdefault` ensures safety.

### WR-05: `sys.path.insert(0, ...)` violates completed SEC-06

**Files modified:** `scripts/setup-channel-branding.py`
**Commit:** `242fc1f`
**Applied fix:** Removed `sys.path.insert(0, str(PROJECT_ROOT))` from module-level code. Imports now rely on the project being installed as a package (`pip install -e .`).

### WR-06: Unprotected import of `validate_or_raise` with inconsistent error handling

**Files modified:** `scripts/setup-channel-branding.py`
**Commit:** `fefd4fd`
**Applied fix:** Moved `from agent_core.core.validation import validate_or_raise` into the existing `try/except ImportError` block alongside the `googleapiclient` imports. Added helpful hint about `pip install -e .` to the error message.

## Skipped Issues

None — all 9 in-scope findings were successfully fixed.

---

_Fixed: 2026-07-14T12:00:00Z_
_Fixer: the agent (gsd-code-fixer)_
_Iteration: 1_
