---
phase: 06-youtube-publishing
reviewed: 2026-07-14T14:30:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - agent_core/publishing/uploader.py
  - agent_core/publishing/metadata.py
  - agent_core/publishing/post_publish.py
findings:
  critical: 0
  warning: 6
  info: 8
  total: 14
status: issues_found
---

# Phase 6: YouTube Publishing — Code Review Report

**Reviewed:** 2026-07-14T14:30:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed three source files implementing YouTube Data API v3 publishing: `uploader.py` (resumable upload, thumbnail, status update, CLI), `metadata.py` (LLM/template SEO metadata generation, chapters, video snippet builder), and `post_publish.py` (playlist assignment/creation, comment posting, metadata/thumbnail updates).

**Overall quality is good** — proper error handling patterns, defensive reads of channel config, consistent use of `get_authenticated_service()` from the OAuth module, and thorough logging. No critical security vulnerabilities found.

**Key concerns:**
1. Dead code in quota-exceeded mid-upload handler (`consume(1600)` on a budget with `daily_limit=6` is always a no-op)
2. `font_display` CSS property incorrectly interpreted as brand tone in LLM prompts
3. `publishAt: null` included unconditionally in metadata.py snippet — may cause API issues
4. Read-modify-write in `update_metadata()` may include read-only fields (thumbnails, channelId)
5. Channel names used directly in filesystem paths with no sanitization (path traversal risk)
6. Thumbnail upload logic duplicated across modules with slightly different validation

---

## Warnings

### WR-01: Dead code — quota.consume(1600) always fails on youtube_upload budget

**File:** `agent_core/publishing/uploader.py:292`
**Issue:** On `HttpError(403, "quotaExceeded")` mid-upload, the code calls `quota.consume("youtube_upload", 1600)`. But the `youtube_upload` budget has `daily_limit=6` (representing upload count, not API units). Since `1600 > 6`, `consume()` always returns `False` without modifying state — this is dead code.

The `QuotaBudget` config defines `youtube_upload` with `daily_limit=6` and comment "YouTube uploads (1,600 units each, 10K daily = ~6/day)". The budget tracks upload *count*, not API *units*. The success path correctly calls `quota.consume("youtube_upload")` (defaults to amount=1). The error path should do the same, or — more likely — should not consume quota at all (the API returns 403 *because* quota is exhausted; the failed request didn't count).

Verified: `quota.consume("youtube_upload", 1600) → False; remaining unchanged`.

**Fix:** Remove the line entirely (don't consume quota on failure), or change to `quota.consume("youtube_upload")` if the intent is to charge 1 upload slot for the failed attempt.

```python
# Option A: Remove — failed uploads should not consume local quota
# (delete line 292)

# Option B: Charge 1 slot if you believe the API consumed it despite error
quota.consume("youtube_upload")
```

### WR-02: `font_display` incorrectly used as brand tone in LLM prompt

**File:** `agent_core/publishing/metadata.py:453`
**Issue:** `channel_config["brand"]["font_display"]` is read as the tone/voice hint for LLM metadata generation. `font_display` is a CSS property (values like `swap`, `auto`, `block`, `fallback`, `optional`) — it describes font rendering behavior, not brand tone. Using it as a tone description will inject meaningless values like `"swap"` or `"auto"` into the LLM prompt where a tone like `"professional"`, `"playful"`, or `"authoritative"` is expected.

**Fix:** Either use a proper tone key from brand config (e.g., `brand.get("tone", "")`) or fall back to `identity.get("tone", "")` only:

```python
# Instead of:
brand_tone = brand.get("font_display", "")  # tone hint from brand

# Use:
brand_tone = brand.get("tone", "")  # proper tone/voice key
```

### WR-03: `publishAt: None` always included in snippet dict

**File:** `agent_core/publishing/metadata.py:756`
**Issue:** `build_video_snippet()` unconditionally sets `"publishAt": None` in the status dict. The YouTube API may reject null values for this field. The uploader's `_build_video_body()` correctly handles this by conditionally adding `publishAt` only when a value is provided (uploader.py:178-179). `build_video_snippet()` should omit the key entirely when no schedule is needed.

**Fix:** Only include `publishAt` when a non-None value is provided:

```python
status = {
    "privacyStatus": privacy,
    "selfDeclaredMadeForKids": False,
    "embeddable": embeddable,
}
# Do NOT set publishAt to None — omit entirely
```

### WR-04: Read-modify-write in `update_metadata()` may include read-only fields

**File:** `agent_core/publishing/post_publish.py:342-364`
**Issue:** `update_metadata()` fetches the full snippet via `videos().list(part="snippet")`, creates a shallow copy with `merged = dict(current)`, then sends the entire merged dict back in `videos().update(part="snippet")`. The API response includes read-only fields (`thumbnails`, `publishedAt`, `channelId`, etc.) that should not be sent back. While the YouTube API often ignores extraneous fields, this is not guaranteed and may cause validation errors or unexpected behavior.

**Fix:** Construct the merged dict with only the updatable fields:

```python
# Instead of:
merged = dict(current)

# Use:
merged = {
    "title": current.get("title", ""),
    "description": current.get("description", ""),
    "tags": current.get("tags", []),
    "categoryId": current.get("categoryId", ""),
    "defaultLanguage": current.get("defaultLanguage", ""),
}
# Then override with provided values
if title is not None:
    merged["title"] = title
# ... etc
```

### WR-05: Path traversal risk via channel name

**File:** All three files (uploader.py:65-74, metadata.py:69-73, post_publish.py:48-57, and OAuth module)
**Issue:** Channel names are used directly in filesystem path construction without sanitization:
```python
return _project_root() / "channels" / channel / "channel_config.json"
```
A channel name like `../..` resolves to the project root, which does exist as a directory, allowing the OAuth token check to "pass" directory existence verification. While file-not-found errors provide some defense, structured channel names like `../../tmp/evil` could access files outside the intended channels directory.

This is low severity since it requires specific target filenames to coincide, but it violates principle of least privilege.

**Fix:** Validate channel names against an allowlist or reject path traversal characters:

```python
import re
if not re.match(r"^[A-Za-z0-9_-]+$", channel):
    raise ValueError(f"Invalid channel name: {channel}")
```

### WR-06: `_ensure_tags` inconsistent stripping behavior

**File:** `agent_core/publishing/post_publish.py:81-94`
**Issue:** When `tags` is a string, it splits by comma and strips each item. When `tags` is a list, it returns items as-is without stripping whitespace. This inconsistency could lead to tags with leading/trailing whitespace when called programmatically with a list.

**Fix:** Strip items when handling list input too:

```python
if isinstance(tags, list):
    return [t.strip() for t in tags if t and t.strip()]
```

---

## Info

### IN-01: Hardcoded "6" as max quota in output messages

**File:** `agent_core/publishing/uploader.py:253-254, 258`
**Issue:** Quota display messages hardcode "6" as the daily upload max:
```python
f"Daily upload quota: 6 max. Remaining: {remaining}/6."
```
If the QuotaBudget defaults file is customized (user gets a quota increase), these messages will be wrong. The max should be read from `QuotaBudget` state or the defaults.

**Fix:**
```python
daily_limit = quota._state["budgets"]["youtube_upload"]["daily_limit"]
print(f"Daily upload quota: {daily_limit} max. Remaining: {remaining}/{daily_limit}.")
```

### IN-02: Thumbnail upload logic duplicated across modules

**File:** `agent_core/publishing/uploader.py:360-387` and `agent_core/publishing/post_publish.py:380-446`
**Issue:** `upload_thumbnail()` in uploader.py and `update_thumbnail()` in post_publish.py implement the same thumbnail upload pattern but with slightly different validation. `post_publish.update_thumbnail()` validates file extension (.jpg/.jpeg/.png), while `uploader.upload_thumbnail()` does not. The post_publish version also has relative-path resolution that the uploader version lacks. This divergence is acknowledged by a TODO in post_publish.py (line 384).

**Fix:** Extract to a shared helper in `agent_core/publishing/uploader.py` and import it in `post_publish.py`.

### IN-03: QuotaBudget instantiated twice in upload flow

**File:** `agent_core/publishing/uploader.py:250, 554`
**Issue:** `main()` creates a `QuotaBudget()` instance at line 554 for pre-flight display, and `upload_video()` creates another at line 250. Each instance reads state from disk. While file locking prevents corruption (via portalocker), this reads and parses the quota file twice per upload invocation. Minor inefficiency.

### IN-04: Description truncated at character boundary

**File:** `agent_core/publishing/metadata.py:270`
**Issue:** `_build_full_description()` truncates at `_DESCRIPTION_MAX_CHARS` (5000) at a character boundary, potentially cutting words mid-word. While unlikely to cause functional issues, it could produce awkward descriptions. `generate_chapters()` handles this better by truncating at line boundaries.

### IN-05: Dict access without `.get()` in CLI output

**File:** `agent_core/publishing/metadata.py:1026-1029`
**Issue:** The CLI's metadata output accesses `metadata["title"]`, `metadata["description"]`, etc., with direct key access instead of `.get()`. While `generate_metadata()` always returns these keys, future code changes could break this assumption. Low risk.

### IN-06: Incorrect docstring for `assign_to_playlist`

**File:** `agent_core/publishing/post_publish.py:124`
**Issue:** Docstring says "Raises: HttpError: If the playlist is not found (404)" but the function catches 404 and returns `False` — it does not raise. The docstring should document the actual return behavior.

### IN-07: `_build_fill_description` parameter name mismatch in docstring

**File:** `agent_core/publishing/metadata.py:240`
**Issue:** Docstring parameter says "Description body from `generate_metadata()`" but the function parameter is named `base_desc`. Minor documentation inconsistency.

### IN-08: Missing `mimetypes.init()` call

**File:** `agent_core/publishing/uploader.py:374`
**Issue:** `mimetypes.guess_type()` is called without first calling `mimetypes.init()`. On some systems, the MIME types database may not be initialized, returning `(None, None)`. The code defaults to `"image/jpeg"` when this happens, so it's not a crash risk, but explicit initialization improves portability.

---

## Summary by Requirement Coverage

| Requirement | Status | Notes |
|---|---|---|
| PUBLISH-02 (Resumable upload, backoff) | ✅ Implemented | 256KB chunks, 5 retries, exponential backoff |
| PUBLISH-04 (LLM metadata) | ✅ Implemented | LLMClient with template fallback |
| PUBLISH-05 (Privacy & scheduling) | ✅ Implemented | publishAt handled, forced private on schedule |
| PUBLISH-06 (Thumbnail upload) | ✅ Implemented | Duplicated (uploader + post_publish) |
| PUBLISH-07 (Channel config) | ✅ Implemented | Cascading fallback from channel_config |
| PUBLISH-09 (Playlist assignment) | ✅ Implemented | assign + create-ensure patterns |
| PUBLISH-10 (Full metadata) | ✅ Implemented | All YouTube API fields covered |
| PUBLISH-11 (Chapter markers) | ✅ Implemented | From checkpoints or custom file |
| PUBLISH-12 (Pin comment) | ⚠️ Partial | Comment creation works; pinning is manual-only (API limitation) |
| PUBLISH-13 (Post-hoc update) | ✅ Implemented | READ-MODIFY-WRITE pattern |

---

## Security Note

No hardcoded credentials, SQL injection vectors, or XSS vulnerabilities found. OAuth tokens are read from per-channel files on disk. API keys are loaded from environment variables. The primary security concern is WR-05 (path traversal via channel name), which is low severity but should be addressed for defense-in-depth.

---

_Reviewed: 2026-07-14T14:30:00Z_
_Reviewer: gsd-code-reviewer (standard depth)_
