---
phase: 06-youtube-publishing
fixed_at: 2026-07-14T03:17:08Z
review_path: .planning/phases/06-youtube-publishing/06-REVIEW.md
iteration: 1
findings_in_scope: 14
fixed: 10
skipped: 4
status: partial
---

# Phase 6: YouTube Publishing — Code Review Fix Report

**Fixed at:** 2026-07-14T03:17:08Z
**Source review:** .planning/phases/06-youtube-publishing/06-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 14 (6 Warning + 8 Info)
- Fixed: 10
- Skipped: 4

## Fixed Issues

### WR-01: Dead code — quota.consume(1600) always fails on youtube_upload budget

**Files modified:** `agent_core/publishing/uploader.py`
**Commit:** cad7067
**Applied fix:** Removed the `quota.consume("youtube_upload", 1600)` call on quota-exceeded mid-upload. Failed uploads due to API quota exhaustion should not consume local quota — the API rejected the request because quota was already exhausted.

### WR-02: `font_display` incorrectly used as brand tone in LLM prompt

**Files modified:** `agent_core/publishing/metadata.py`
**Commit:** 4125f92
**Applied fix:** Changed `brand.get("font_display", "")` to `brand.get("tone", "")` to use the proper brand tone/voice configuration key instead of the CSS `font-display` property.

### WR-03: `publishAt: None` always included in snippet dict

**Files modified:** `agent_core/publishing/metadata.py`
**Commit:** 318eb58
**Applied fix:** Removed `"publishAt": None` from the status dict in `build_video_snippet()`. The uploader's `_build_video_body()` already handles conditional publishAt insertion. A null value may cause YouTube API rejection.

### WR-04: Read-modify-write in `update_metadata()` may include read-only fields

**Files modified:** `agent_core/publishing/post_publish.py`
**Commit:** 8ba3f29
**Applied fix:** Replaced `merged = dict(current)` with a filtered dict containing only mutable fields (`title`, `description`, `tags`, `categoryId`, `defaultLanguage`). Read-only fields like `thumbnails`, `channelId`, and `publishedAt` are no longer sent back in the update request.

### WR-05: Path traversal risk via channel name

**Files modified:** `agent_core/publishing/uploader.py`, `agent_core/publishing/metadata.py`, `agent_core/publishing/post_publish.py`
**Commit:** 9aed10c
**Applied fix:** Added `_validate_channel()` helper function using `re.match(r"^[A-Za-z0-9_-]+$", channel)` to all three files. Validation is applied:
- In `_channel_config_path()` (and other path-constructing functions like `_brain_path`)
- In `_load_channel_config()` and `_load_brain()` with ValueError handling
- In `main()` CLI entry points for early feedback with clear error message

### WR-06: `_ensure_tags` inconsistent stripping behavior

**Files modified:** `agent_core/publishing/post_publish.py`
**Commit:** 732f4b6
**Applied fix:** Added consistent whitespace stripping for list inputs: `[t.strip() for t in tags if t and t.strip()]`. Previously only string inputs were stripped; list inputs passed through as-is.

### IN-01: Hardcoded "6" as max quota in output messages

**Files modified:** `agent_core/publishing/uploader.py`
**Commit:** a32d4f0
**Applied fix:** Replaced all hardcoded `"6"` references with dynamic `daily_limit` read from `quota.get_summary()` state. Affected messages in both `upload_video()` and `main()` pre-flight quota display and dry-run output.

### IN-04: Description truncated at character boundary

**Files modified:** `agent_core/publishing/metadata.py`
**Commit:** 6c87a82
**Applied fix:** After truncating at `_DESCRIPTION_MAX_CHARS`, find the last space boundary and truncate there to avoid cutting words mid-word.

### IN-05: Dict access without `.get()` in CLI output

**Files modified:** `agent_core/publishing/metadata.py`
**Commit:** 6c87a82
**Applied fix:** Changed `metadata["title"]`, `metadata["description"]`, `metadata["tags"]`, `metadata["category_id"]` to use `.get()` with sensible defaults in both the dry-run save and persist blocks of `main()` CLI.

### IN-08: Missing `mimetypes.init()` call

**Files modified:** `agent_core/publishing/uploader.py`, `agent_core/publishing/post_publish.py`
**Commit:** ad83801
**Applied fix:** Added `mimetypes.init()` before each `mimetypes.guess_type()` call in both `upload_thumbnail()` (uploader.py) and `update_thumbnail()` (post_publish.py) to ensure the MIME types database is initialized.

## Skipped Issues

### IN-02: Thumbnail upload logic duplicated across modules

**Files:** `agent_core/publishing/uploader.py`, `agent_core/publishing/post_publish.py`
**Reason:** Extracting shared thumbnail upload logic is a significant refactoring task, not a targeted bug fix. The differing path resolution and validation behaviors would require changing both callers and signatures, introducing risk of regression. A TODO already exists in post_publish.py flagging this. Best addressed as a separate refactoring phase.

### IN-03: QuotaBudget instantiated twice in upload flow

**Files:** `agent_core/publishing/uploader.py`
**Reason:** Minor optimization only — each instance reads from disk but file locking prevents corruption. The double-read is negligible overhead per upload invocation. Not a bug; fixing would require refactoring the function signature to accept an optional QuotaBudget instance.

### IN-06: Incorrect docstring for `assign_to_playlist`

**Files:** `agent_core/publishing/post_publish.py`
**Reason:** The docstring already correctly documents the return behavior (`Returns False if not found, quota exceeded, or error occurred`). No `Raises:` section exists in the actual source — the review may have been based on an older version. No fix needed.

### IN-07: `_build_fill_description` parameter name mismatch in docstring

**Files:** `agent_core/publishing/metadata.py`
**Reason:** The function `_build_full_description` already has the correct docstring with `base_desc:` as the documented parameter name matching the actual parameter. The review noted a mismatch that does not exist in the current code. No fix needed.

---

_Fixed: 2026-07-14T03:17:08Z_
_Fixer: the agent (gsd-code-fixer)_
_Iteration: 1_
