# Hardcoded API Provider Audit

**Audit Date:** 2026-07-09

---

## Provider: OpenAI

### Purpose
LLM chat inference (skeleton extraction, pattern synthesis, entity extraction), speech-to-text transcription (Whisper API), and Reddit discovery via Responses API (web_search tool with model-based search).

### Configuration
- **API Key env var:** `OPENAI_API_KEY` — read in `recon/config.py:83`, `skins/last30days/scripts/lib/env.py:54`, and `recon/skeleton_ripper/pipeline.py:203`
- **Base URL:** `https://api.openai.com/v1` (hardcoded in `recon/skeleton_ripper/llm_client.py:37`) — NOT configurable at runtime
- **Additional endpoints used:**
  - `https://api.openai.com/v1/chat/completions` — `recon/skeleton_ripper/llm_client.py:136`
  - `https://api.openai.com/v1/audio/transcriptions` — `recon/scraper/downloader.py:48`
  - `https://api.openai.com/v1/responses` — `skills/last30days/scripts/lib/openai_reddit.py:44`
  - `https://api.openai.com/v1/models` — `skills/last30days/scripts/lib/models.py:9`
- **Auth method:** Bearer token in `Authorization: Bearer {key}` header

### Endpoints Called
| Endpoint | Purpose | Location |
|---|---|---|
| `POST /v1/chat/completions` | LLM chat for skeleton extraction & pattern synthesis | `recon/skeleton_ripper/llm_client.py:136-140` |
| `POST /v1/audio/transcriptions` | Whisper speech-to-text transcription | `recon/scraper/downloader.py:48-60` |
| `POST /v1/responses` | Reddit search via OpenAI "Responses API" with web_search tool | `skills/last30days/scripts/lib/openai_reddit.py:44,186` |
| `GET /v1/models` | List available models for auto-selection | `skills/last30days/scripts/lib/models.py:9,82` |

### Request Format

**Chat completions (recon/skeleton_ripper/llm_client.py:130-142):**
- Method: POST
- Headers: `{"Authorization": "Bearer {key}", "Content-Type": "application/json"}`
- Body: `{"model": <model>, "messages": [...], "temperature": <float>}`
- SDK: Raw `requests.post()` — no official OpenAI SDK

**Whisper transcription (recon/scraper/downloader.py:48-60):**
- Method: POST
- Headers: `{"Authorization": "Bearer {key}"}`
- Body: multipart form with `file` (binary), `model: "whisper-1"`, `language: "en"`, `response_format: "text"`
- SDK: Raw `requests.post()` with multipart upload

**Responses API (skills/last30days/scripts/lib/openai_reddit.py:170-186):**
- Method: POST
- Headers: `{"Authorization": "Bearer {key}", "Content-Type": "application/json"}`
- Body: `{"model": <model>, "tools": [{"type": "web_search", "filters": {"allowed_domains": ["reddit.com"]}}], "include": [...], "input": ...}`
- SDK: Custom `http.post()` wrapper over `urllib.request`

### Usage Locations
- `recon/skeleton_ripper/llm_client.py:36-42` — Provider config with models list
- `recon/skeleton_ripper/llm_client.py:100-101,130-142` — OpenAI chat call routing + implementation
- `recon/scraper/downloader.py:29-96` — `transcribe_video_openai()` function
- `recon/config.py:35,83,114` — API key loading
- `recon/skeleton_ripper/pipeline.py:203,304-305` — Transcription orchestrator
- `skills/last30days/scripts/lib/openai_reddit.py:44,119-202` — Reddit search via Responses API
- `skills/last30days/scripts/lib/models.py:9,51-107` — Model auto-selection with caching
- `skills/last30days/scripts/lib/env.py:54` — LAST30DAYS_CONFIG_DIR env var name

### Hardcoded Assumptions
- `model: "gpt-4o-mini"` hardcoded as default in `recon/config.py:37` and `recon/skeleton_ripper/pipeline.py:81`
- `model: "whisper-1"` hardcoded in `recon/scraper/downloader.py:56`
- `language: "en"` hardcoded for Whisper in `recon/scraper/downloader.py:56`
- `response_format: "text"` hardcoded in `recon/scraper/downloader.py:56`
- Fallback model order hardcoded: `["gpt-4.1", "gpt-4o"]` in `skills/last30days/scripts/lib/openai_reddit.py:12`
- Fallback model list hardcoded: `["gpt-5.2", "gpt-5.1", "gpt-5", "gpt-4.1", "gpt-4o"]` in `skills/last30days/scripts/lib/models.py:10`
- Retryable status codes hardcoded: `{429, 500, 502, 503, 504}` in `recon/skeleton_ripper/llm_client.py:73`
- Max retries: 3 (`recon/skeleton_ripper/llm_client.py:72`)
- Timeout: 120s by default (`recon/skeleton_ripper/llm_client.py:75`)
- Rate limit assumed: 429 response, exponential backoff in `recon/scraper/downloader.py:73-75`
- Allowed domains filter hardcoded to `["reddit.com"]` in `skills/last30days/scripts/lib/openai_reddit.py:177`

---

## Provider: Anthropic

### Purpose
Alternative LLM chat inference for skeleton extraction and pattern synthesis in the recon module.

### Configuration
- **API Key env var:** `ANTHROPIC_API_KEY` — read in `recon/config.py:84` and `recon/skeleton_ripper/llm_client.py:44`
- **Base URL:** `https://api.anthropic.com/v1` (hardcoded in `recon/skeleton_ripper/llm_client.py:45`) — NOT configurable at runtime
- **Auth method:** `x-api-key` header (NOT Bearer) — `recon/skeleton_ripper/llm_client.py:153`

### Endpoints Called
| Endpoint | Purpose | Location |
|---|---|---|
| `POST /v1/messages` | Chat completions | `recon/skeleton_ripper/llm_client.py:151-157` |

### Request Format
```python
# recon/skeleton_ripper/llm_client.py:144-157
payload = {
    "model": self.model,
    "max_tokens": 4096,                    # Hardcoded limit
    "temperature": temperature,
    "messages": [{"role": "user", "content": user_prompt}]
    # "system" key added if system_prompt provided
}
headers = {
    "x-api-key": self.api_key,
    "anthropic-version": "2023-06-01",     # Hardcoded version
    "Content-Type": "application/json"
}
```

### Usage Locations
- `recon/skeleton_ripper/llm_client.py:43-50` — Provider config with models list
- `recon/skeleton_ripper/llm_client.py:102-103,144-157` — Anthropic chat call + implementation

### Hardcoded Assumptions
- `max_tokens: 4096` hardcoded in `recon/skeleton_ripper/llm_client.py:146`
- `anthropic-version: "2023-06-01"` hardcoded in `recon/skeleton_ripper/llm_client.py:153`
- Models hardcoded: `claude-3-haiku-20240307` (low cost), `claude-3-sonnet-20240229` (medium cost) — `recon/skeleton_ripper/llm_client.py:47-49`
- Response format: expects JSON path `response.json()['content'][0]['text']` — `recon/skeleton_ripper/llm_client.py:157`
- No model auto-selection — models are static config
- No streaming support

---

## Provider: Google / Gemini

### Purpose
Alternative LLM chat inference for skeleton content extraction in the recon module.

### Configuration
- **API Key env var:** `GOOGLE_API_KEY` — read in `recon/config.py:85`
- **Base URL:** `https://generativelanguage.googleapis.com/v1beta` (hardcoded in `recon/skeleton_ripper/llm_client.py:53`) — NOT configurable at runtime
- **Auth method:** API key passed as URL query parameter `?key={key}` — `recon/skeleton_ripper/llm_client.py:162`

### Endpoints Called
| Endpoint | Purpose | Location |
|---|---|---|
| `POST /v1beta/models/{model}:generateContent?key={key}` | Text generation | `recon/skeleton_ripper/llm_client.py:161-168` |

### Request Format
```python
# recon/skeleton_ripper/llm_client.py:159-168
full_prompt = system_prompt + "\n\n---\n\n" + user_prompt  # Manual concatenation
response = requests.post(
    f"{base_url}/models/{model}:generateContent?key={api_key}",
    headers={"Content-Type": "application/json"},
    json={
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"temperature": temperature}
    },
    timeout=self.timeout
)
```

### Usage Locations
- `recon/skeleton_ripper/llm_client.py:51-58` — Provider config with models list
- `recon/skeleton_ripper/llm_client.py:104-105,159-168` — Google chat call + implementation

### Hardcoded Assumptions
- System prompt and user prompt manually concatenated with `"\n\n---\n\n"` separator — NOT using Gemini's native `system_instruction` field
- Models hardcoded: `gemini-1.5-flash` (low), `gemini-1.5-pro` (medium) — `recon/skeleton_ripper/llm_client.py:55-57`
- Response expects `response.json()['candidates'][0]['content']['parts'][0]['text']` — `recon/skeleton_ripper/llm_client.py:168`
- API key sent as query param (less secure than header)
- No `generationConfig` for safety settings, stop sequences, etc.
- Auth mechanism (query param key) is the deprecated API key method, not OAuth

---

## Provider: Ollama (Local)

### Purpose
Local LLM inference for skeleton content extraction, runs on localhost with no API key.

### Configuration
- **API Key env var:** None — no auth required
- **Base URL:** `http://localhost:11434/api` (hardcoded in `recon/skeleton_ripper/llm_client.py:61`) — NOT configurable at runtime
- **Auth method:** None

### Endpoints Called
| Endpoint | Purpose | Location |
|---|---|---|
| `POST /api/generate` | Text generation | `recon/skeleton_ripper/llm_client.py:172-178` |
| `GET /api/tags` | List installed models | `recon/skeleton_ripper/llm_client.py:188` |

### Request Format
```python
# recon/skeleton_ripper/llm_client.py:170-178
response = requests.post(
    f"{base_url}/generate",
    json={
        "model": self.model,
        "prompt": full_prompt,
        "stream": False,
        "options": {"temperature": temperature}
    },
    timeout=self.timeout
)
```

### Usage Locations
- `recon/skeleton_ripper/llm_client.py:59-68` — Provider config with models list
- `recon/skeleton_ripper/llm_client.py:106-107,170-178` — Ollama chat call + implementation
- `recon/skeleton_ripper/llm_client.py:186-196` — Model availability check

### Hardcoded Assumptions
- `localhost:11434` — assumes Ollama running locally on default port
- Models hardcoded: `qwen3` (recommended), `llama3`, `mistral` — `recon/skeleton_ripper/llm_client.py:63-65`
- `stream: False` hardcoded — `recon/skeleton_ripper/llm_client.py:174`
- Response expects `response.json()['response']` — `recon/skeleton_ripper/llm_client.py:178`

---

## Provider: xAI (Grok / X Search)

### Purpose
LLM-powered X/Twitter discovery using xAI's Responses API with the `x_search` agent tool.

### Configuration
- **API Key env var:** `XAI_API_KEY` — read in `skills/last30days/scripts/lib/env.py:55`
- **Base URL:** `https://api.x.ai/v1` — used in two places:
  - `https://api.x.ai/v1/responses` — `skills/last30days/scripts/lib/xai_x.py:17`
  - `https://api.x.ai/v1/models` — `skills/last30days/scripts/lib/models.py:13`
- **Auth method:** Bearer token in `Authorization: Bearer {key}` header — `skills/last30days/scripts/lib/xai_x.py:87`

### Endpoints Called
| Endpoint | Purpose | Location |
|---|---|---|
| `POST /v1/responses` | X search via `x_search` tool | `skills/last30days/scripts/lib/xai_x.py:17,114` |
| `GET /v1/models` | List available models | `skills/last30days/scripts/lib/models.py:13,82` |

### Request Format
```python
# skills/last30days/scripts/lib/xai_x.py:95-114
payload = {
    "model": model,
    "tools": [{"type": "x_search"}],
    "input": [{"role": "user", "content": X_SEARCH_PROMPT.format(...)}],
}
```

### Usage Locations
- `skills/last30days/scripts/lib/xai_x.py:17,58-114` — Full search implementation
- `skills/last30days/scripts/lib/models.py:110-144` — Model auto-selection (XAI aliases)
- `skills/last30days/scripts/lib/env.py:55` — Config loading

### Hardcoded Assumptions
- `model: "grok-4-1-fast"` hardcoded as the only alias for `latest`/`stable` in `skills/last30days/scripts/lib/models.py:15-16`
- Tool `x_search` assumes xAI has agentic X search capability — proprietary
- Depth config hardcoded: quick (8-12), default (20-30), deep (40-60) — `skills/last30days/scripts/lib/xai_x.py:20-23`
- Timeouts: 90s/120s/180s — `skills/last30days/scripts/lib/xai_x.py:92`
- Response parsing expects OpenAI-compatible `/v1/responses` output structure — `skills/last30days/scripts/lib/xai_x.py:117-216`
- Model configs are aliases (`latest`→`grok-4-1-fast`), not actual API listing

---

## Provider: OpenRouter / Perplexity Sonar Pro

### Purpose
Web search via Perplexity's Sonar Pro model proxied through OpenRouter's chat completions endpoint.

### Configuration
- **API Key env var:** `OPENROUTER_API_KEY` — read in `skills/last30days/scripts/lib/env.py:56`
- **Base URL:** `https://openrouter.ai/api/v1/chat/completions` (hardcoded in `skills/last30days/scripts/lib/openrouter_search.py:18`) — NOT configurable at runtime
- **Auth method:** Bearer token in `Authorization: Bearer {key}` header — `skills/last30days/scripts/lib/openrouter_search.py:73`

### Endpoints Called
| Endpoint | Purpose | Location |
|---|---|---|
| `POST /api/v1/chat/completions` | Perplexity Sonar Pro with built-in web search | `skills/last30days/scripts/lib/openrouter_search.py:18,69-78` |

### Request Format
```python
# skills/last30days/scripts/lib/openrouter_search.py:60-78
payload = {
    "model": "perplexity/sonar-pro",
    "messages": [{"role": "user", "content": prompt}],
    "max_tokens": max_tokens,
}
headers = {
    "Authorization": "Bearer {api_key}",
    "HTTP-Referer": "https://github.com/mvanhorn/last30days-openclaw",
    "X-Title": "last30days",
}
```

### Usage Locations
- `skills/last30days/scripts/lib/openrouter_search.py` — Entire file
- `skills/last30days/scripts/lib/env.py:114-115` — Source detection

### Hardcoded Assumptions
- `model: "perplexity/sonar-pro"` hardcoded in `skills/last30days/scripts/lib/openrouter_search.py:19`
- `HTTP-Referer` hardcoded to a specific GitHub URL — `skills/last30days/scripts/lib/openrouter_search.py:74`
- `X-Title: "last30days"` hardcoded — `skills/last30days/scripts/lib/openrouter_search.py:75`
- Excluded domains: `reddit.com`, `twitter.com`, `x.com` — `skills/last30days/scripts/lib/openrouter_search.py:22-25`
- Max tokens: quick=1024, default=2048, deep=4096 — `skills/last30days/scripts/lib/openrouter_search.py:50`
- Response format expects OpenRouter's chat completions schema (may differ from OpenAI's)
- Parses both `search_results` and `citations` fields — assumes Sonar Pro proprietary response shape

---

## Provider: Brave Search

### Purpose
Web search fallback API for finding blogs, news, and articles.

### Configuration
- **API Key env var:** `BRAVE_API_KEY` — read in `skills/last30days/scripts/lib/env.py:58`
- **Base URL:** `https://api.search.brave.com/res/v1/web/search` (hardcoded in `skills/last30days/scripts/lib/brave_search.py:18`) — NOT configurable at runtime
- **Auth method:** `X-Subscription-Token` header — `skills/last30days/scripts/lib/brave_search.py:77`

### Endpoints Called
| Endpoint | Purpose | Location |
|---|---|---|
| `GET /res/v1/web/search?q={topic}&result_filter=web,news&...` | Web + news search | `skills/last30days/scripts/lib/brave_search.py:18,74-79` |

### Request Format
```python
# skills/last30days/scripts/lib/brave_search.py:58-79
params = {
    "q": topic,
    "result_filter": "web,news",
    "count": count,                        # 8/15/25 based on depth
    "safesearch": "strict",
    "text_decorations": 0,
    "spellcheck": 0,
}
# freshness added conditionally based on date range
url = f"{ENDPOINT}?{urlencode(params)}"
response = http.request("GET", url, headers={"X-Subscription-Token": api_key}, timeout=15)
```

### Usage Locations
- `skills/last30days/scripts/lib/brave_search.py` — Entire file
- `skills/last30days/scripts/lib/env.py:112` — Source detection

### Hardcoded Assumptions
- `safesearch: "strict"` hardcoded — `skills/last30days/scripts/lib/brave_search.py:62`
- `text_decorations: 0` (no markdown in results) — `skills/last30days/scripts/lib/brave_search.py:63`
- `spellcheck: 0` — `skills/last30days/scripts/lib/brave_search.py:64`
- Result counts: 8/15/25 — `skills/last30days/scripts/lib/brave_search.py:52`
- Freshness codes: `pd`=24h, `pw`=7d, `pm`=31d — `skills/last30days/scripts/lib/brave_search.py:21`
- Excluded domains: `reddit.com`, `twitter.com`, `x.com` — `skills/last30days/scripts/lib/brave_search.py:24-27`
- Response shape expects `{"web":{"results":[...]}, "news":{"results":[...]}}` — Brave's API v1 structure

---

## Provider: Parallel AI

### Purpose
LLM-optimized web search API (preferred web search backend).

### Configuration
- **API Key env var:** `PARALLEL_API_KEY` — read in `skills/last30days/scripts/lib/env.py:57`
- **Base URL:** `https://api.parallel.ai/v1beta/search` (hardcoded in `skills/last30days/scripts/lib/parallel_search.py:17`) — NOT configurable at runtime
- **Auth method:** Bearer token in `Authorization: Bearer {key}` header — `skills/last30days/scripts/lib/parallel_search.py:67`

### Endpoints Called
| Endpoint | Purpose | Location |
|---|---|---|
| `POST /v1beta/search` | Web search with LLM-optimized excerpts | `skills/last30days/scripts/lib/parallel_search.py:17,63-71` |

### Request Format
```python
# skills/last30days/scripts/lib/parallel_search.py:50-71
payload = {
    "objective": "Find recent blog posts, tutorials, ...",
    "max_results": max_results,     # 8/15/25 based on depth
    "max_chars_per_result": 500,
}
headers = {
    "Authorization": "Bearer {api_key}",
    "parallel-beta": "search-extract-2025-10-10",   # Hardcoded beta header
}
```

### Usage Locations
- `skills/last30days/scripts/lib/parallel_search.py` — Entire file
- `skills/last30days/scripts/lib/env.py:110-111` — Source selection (highest priority)

### Hardcoded Assumptions
- `max_chars_per_result: 500` hardcoded — `skills/last30days/scripts/lib/parallel_search.py:57`
- `parallel-beta: "search-extract-2025-10-10"` hardcoded beta header — `skills/last30days/scripts/lib/parallel_search.py:68`
- Excluded domains: `reddit.com`, `twitter.com`, `x.com` — `skills/last30days/scripts/lib/parallel_search.py:20-23`
- Response shape expects `{"results": [{"url", "title", "excerpt", "published_date", "relevance_score"}]}`

---

## Provider: Instagram Graph API (Meta/Facebook)

### Purpose
Per-post/reel analytics: views, reach, likes, comments, shares, saves, engagement rate, follower growth.

### Configuration
- **API Key env vars:** `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ACCOUNT_ID` — loaded from `.env` via `load_env()` in `scripts/fetch-ig-insights.py:222-223`
- **Base URL:** `https://graph.facebook.com/v21.0` — hardcoded in both `scripts/fetch-ig-insights.py:37` and `scripts/setup-ig-token.py:37`
- **Auth method:** `access_token={token}` query parameter — `scripts/fetch-ig-insights.py:57,58,86,87,123,198,199`

### Endpoints Called
| Endpoint | Purpose | Location |
|---|---|---|
| `GET /{BASE_URL}/{media_id}` | Media metadata (caption, timestamp, likes, comments) | `scripts/fetch-ig-insights.py:53-63` |
| `GET /{BASE_URL}/{media_id}/insights` | Rich metrics (reach, plays, saves, shares, total_interactions) | `scripts/fetch-ig-insights.py:83-91, 118-127` |
| `GET /{BASE_URL}/{account_id}/insights` | Account-level follower count over time | `scripts/fetch-ig-insights.py:163-179` |
| `GET /{BASE_URL}/{account_id}/media` | List recent media IDs | `scripts/fetch-ig-insights.py:197-208` |
| `GET /{BASE_URL}/oauth/access_token` | OAuth token exchange | `scripts/setup-ig-token.py:108-117,127-135` |
| `GET /{BASE_URL}/me/accounts` | Find Instagram Business Account linked to Facebook Page | `scripts/setup-ig-token.py:148-155` |

### Request Format
All calls use raw `requests.get()` with query parameters. No SDK.
```python
# scripts/fetch-ig-insights.py:54-62
response = requests.get(
    f"{BASE_URL}/{media_id}",
    params={"access_token": access_token, "fields": "id,caption,timestamp,media_type,like_count,comments_count,permalink"},
    timeout=15
)
```

### Usage Locations
- `scripts/fetch-ig-insights.py:36-154` — Full insights fetch implementation
- `scripts/setup-ig-token.py:36-190` — OAuth token setup flow

### Hardcoded Assumptions
- API version `v21.0` hardcoded — `scripts/fetch-ig-insights.py:36`, `scripts/setup-ig-token.py:36`
- Media metrics: `reach,saved,shares,plays,total_interactions` for VIDEO/REELS — `scripts/fetch-ig-insights.py:80`
- Media metrics: `reach,saved,shares,total_interactions` for IMAGE — `scripts/fetch-ig-insights.py:123`
- Follower delta window: -1 day to +2 days around publish — `scripts/fetch-ig-insights.py:166-167`
- OAuth scopes hardcoded: `instagram_basic,instagram_manage_insights,pages_show_list,pages_read_engagement` — `scripts/setup-ig-token.py:84`
- Redirect URI hardcoded to `https://localhost/` — `scripts/setup-ig-token.py:83,113`
- Token lifetime assumption: 60 days (`5184000` seconds) — `scripts/setup-ig-token.py:143`
- Expects `IGP_EXCHANGE_TOKEN` response format — `scripts/setup-ig-token.py:123,142`

---

## Provider: YouTube Data API v3 + YouTube Analytics API

### Purpose
Per-video metadata (views, likes, comments, duration, thumbnails) via Data API, plus rich analytics (watch time, avg view duration, subscribers gained) via Analytics API (OAuth).

### Configuration
- **API Key env var:** `YOUTUBE_DATA_API_KEY` — loaded from `.env` in `scripts/fetch-yt-analytics.py:222-223`
- **OAuth token:** Saved to `~/.viral-command/yt-token.json` — loaded in `scripts/fetch-yt-analytics.py:51-79`
- **Base URLs:**
  - `https://www.googleapis.com/youtube/v3` — Data API v3, hardcoded in `scripts/fetch-yt-analytics.py:95`
  - `https://youtubeanalytics.googleapis.com/v2` — Analytics API, hardcoded in `scripts/fetch-yt-analytics.py:144,189`
- **Auth methods:** API key as query param `key={key}` (Data API), Bearer token (Analytics API OAuth)

### Endpoints Called
| Endpoint | Purpose | Location |
|---|---|---|
| `GET /youtube/v3/videos?part=statistics,snippet,contentDetails&id={video_id}&key={key}` | Video metadata | `scripts/fetch-yt-analytics.py:95-102` |
| `GET /youtubeanalytics/v2/reports?ids=channel==MINE&metrics=...&filters=video=={id}` | Analytics metrics | `scripts/fetch-yt-analytics.py:144-151, 189-196` |

### Request Format
```python
# scripts/fetch-yt-analytics.py:95-102 (Data API)
params = {
    "part": "statistics,snippet,contentDetails",
    "id": video_id,
    "key": api_key,
}
resp = requests.get("https://www.googleapis.com/youtube/v3/videos", params=params, timeout=15)

# scripts/fetch-yt-analytics.py:144-155 (Analytics API, OAuth)
params = {
    "ids": "channel==MINE",
    "startDate": pub_date,
    "endDate": end_date,
    "metrics": "estimatedMinutesWatched,averageViewDuration,subscribersGained",
    "filters": f"video=={video_id}",
}
headers = {"Authorization": f"Bearer {oauth_token}"}
resp = requests.get("https://youtubeanalytics.googleapis.com/v2/reports", params=params, headers=headers, timeout=15)
```

### Usage Locations
- `scripts/fetch-yt-analytics.py:82-178` — Full fetch implementation (Data + Analytics)
- `scripts/setup-yt-oauth.py:1-73` — OAuth setup flow

### Hardcoded Assumptions
- Data API `part` parameters: `statistics,snippet,contentDetails` — `scripts/fetch-yt-analytics.py:97`
- Duration > 180s = `youtube_longform`, ≤ 180s = `youtube_shorts` — `scripts/fetch-yt-analytics.py:127`
- Thumbnail priority: `maxres`→`high`→`medium`→`default` — `scripts/fetch-yt-analytics.py:118-120`
- Analytics metrics: `estimatedMinutesWatched,averageViewDuration,subscribersGained` — `scripts/fetch-yt-analytics.py:149`
- Analytics OAuth scopes: `yt-analytics.readonly`, `youtube.readonly` — `scripts/setup-yt-oauth.py:27-28`
- OAuth port: 8080 — `scripts/setup-yt-oauth.py:54`
- Token saved to `~/.viral-command/yt-token.json` — `scripts/fetch-yt-analytics.py:38`
- `client_secret.json` expected at `scripts/client_secret.json` — `scripts/setup-yt-oauth.py:33`
- `channel==MINE` assumes the OAuth user owns the channel — `scripts/fetch-yt-analytics.py:146`

---

## Provider: Reddit (free JSON endpoints)

### Purpose
Supplemental search across specific subreddits and thread enrichment (engagement metrics, comments). No API key needed.

### Configuration
- **API Key:** None — uses Reddit's unauthenticated JSON endpoints
- **Base URL:** `https://www.reddit.com` — hardcoded in:
  - `skills/last30days/scripts/lib/openai_reddit.py:233` (`/r/{sub}/search/.json`)
  - `skills/last30days/scripts/lib/http.py:160` (general `.json reddit URL)
- **Auth method:** None — relies on `User-Agent` header for rate limiting

### Endpoints Called
| Endpoint | Purpose | Location |
|---|---|---|
| `GET /r/{subreddit}/search/.json?q={}&restrict_sr=on&sort=new&limit={}` | Subreddit search (no auth) | `skills/last30days/scripts/lib/openai_reddit.py:233-235` |
| `GET /r/{subreddit}/comments/{id}/{title}.json` | Thread data + comments | `skills/last30days/scripts/lib/http.py:160`, `skills/last30days/scripts/lib/reddit_enrich.py:61` |

### Request Format
```python
# skills/last30days/scripts/lib/openai_reddit.py:233-242
url = f"https://www.reddit.com/r/{sub}/search/.json"
full_url = f"{url}?{params}"
headers = {"User-Agent": last30days-skill/2.1, "Accept": "application/json"}
data = http.get(full_url, headers=headers, timeout=15, retries=1)

# skills/last30days/scripts/lib/http.py:160
url = f"https://www.reddit.com{path}?raw_json=1"
```

### Usage Locations
- `skills/last30days/scripts/lib/openai_reddit.py:205-286` — `search_subreddits()` function
- `skills/last30days/scripts/lib/reddit_enrich.py:33-66` — `fetch_thread_data()` function
- `skills/last30days/scripts/lib/http.py:140-167` — `get_reddit_json()` helper

### Hardcoded Assumptions
- `User-Agent: "last30days-skill/2.1 (Assistant Skill)"` hardcoded in `skills/last30days/scripts/lib/http.py:23`
- Rate limit behavior: 429 status → stop remaining searches — `skills/last30days/scripts/lib/openai_reddit.py:274-275`
- Reddit JSON response has `{"data": {"children": [{"kind": "t3", "data": {...}}]}}` structure — `skills/last30days/scripts/lib/openai_reddit.py:244-250`
- Thread JSON is `[submission_listing, comments_listing]` array — `skills/last30days/scripts/lib/reddit_enrich.py:83-104`
- Sort: `new` for subreddit search — `skills/last30days/scripts/lib/openai_reddit.py:234`
- `restrict_sr=on` to limit to subreddit — `skills/last30days/scripts/lib/openai_reddit.py:234`
- Max 5 results per subreddit (`count_per=5`) — `skills/last30days/scripts/lib/openai_reddit.py:211`
- No rate limit sleep between requests (only stops on 429)

---

## Provider: Bird X Search (Twitter GraphQL via Node.js)

### Purpose
Free X/Twitter search via vendored GraphQL client (`@steipete/bird`). Alternative to xAI's paid API.

### Configuration
- **API Key:** None — uses Twitter cookies/auth from the local machine (browser or env vars)
- **No env var needed**, but checks `AUTH_TOKEN` env var via the Bird CLI
- **Base URL:** Not applicable — all logic is in a vendored Node.js module at `skills/last30days/scripts/lib/vendor/bird-search/bird-search.mjs`
- **Auth method:** Twitter session cookies (extracted from browser or set via `AUTH_TOKEN` env var) — handled by the vendored Bird module

### Request Format
```python
# skills/last30days/scripts/lib/bird_x.py:173-176
cmd = [
    "node", str(_BIRD_SEARCH_MJS),
    query,                    # e.g., "claude code since:2026-06-09"
    "--count", str(count),  # 12/30/60 based on depth
    "--json",
]
```

### Usage Locations
- `skills/last30days/scripts/lib/bird_x.py:162-229` — Full search implementation via subprocess
- `skills/last30days/scripts/lib/bird_x.py:273-346` — Handle-targeted search (`search_handles()`)
- `skills/last30days/scripts/lib/bird_x.py:349-436` — Response parsing
- `skills/last30days/scripts/lib/env.py:229-240` — Status and source detection

### Hardcoded Assumptions
- Requires `node` in PATH — `skills/last30days/scripts/lib/bird_x.py:97`
- Assumes Node.js 22+ — `skills/last30days/scripts/lib/bird_x.py:91`
- Timeouts: 30s (quick), 45s (default), 60s (deep) — `skills/last30days/scripts/lib/bird_x.py:250`
- Depth result counts: 12/30/60 — `skills/last30days/scripts/lib/bird_x.py:21-24`
- Queries use `since:{from_date}` format — `skills/last30days/scripts/lib/bird_x.py:254`
- Parses multiple date formats from Bird: ISO 8601 and Twitter's `"%a %b %d %H:%M:%S %z %Y"` — `skills/last30days/scripts/lib/bird_x.py:389-401`
- Engagement fields: camelCase + snake_case variants (likeCount/like_count) — `skills/last30days/scripts/lib/bird_x.py:408-413`
- Bird response can be either a list or `{"items": [...], "tweets": [...]}` — flexible handling
- Kill signal: `SIGTERM` → process group — `skills/last30days/scripts/lib/bird_x.py:204`

---

## Provider: bird-search.mjs (Vendored Node.js Module)

### Purpose
Twitter GraphQL search bridge. The .mjs file is the actual API client that talks to Twitter's internal GraphQL endpoint.

### Configuration
- **Auth:** X cookies (browser-detected or `AUTH_TOKEN` env var)
- **Target URL:** Twitter's own GraphQL API (not documented — reverse-engineered) — inside `bird-search.mjs`
- **NOT configurable** — vendored npm module (`@steipete/bird` v0.8.0, MIT Licensed)

### Location
- `skills/last30days/scripts/lib/vendor/bird-search/bird-search.mjs`

---

## Provider: Instaloader (Instagram Scraper)

### Purpose
Fetch Instagram reel metadata and download video content for competitor analysis.

### Configuration
- **Credentials:** `IG_USERNAME` / `IG_PASSWORD` env vars — read in `recon/config.py:81-82`
- **Base URL:** N/A — uses the `instaloader` Python package (wrapper around Instagram's private API)
- **Auth method:** Session-based login via `instaloader.Instaloader.login()` — `recon/scraper/instagram.py:76`
- **SDK:** `instaloader` Python package — `recon/scraper/instagram.py:18`

### Endpoints Called
N/A — all API interactions are internal to the `instaloader` package

### Usage Locations
- `recon/scraper/instagram.py:28-242` — `InstaClient` class
- `recon/skeleton_ripper/pipeline.py:215-256` — Pipeline orchestrator

### Hardcoded Assumptions
- Instaloader settings: downloads videos, no geotags, no comments, no metadata files, quiet mode — `recon/scraper/instagram.py:34-42`
- Session saved to `data/recon/.session_{username}` — `recon/scraper/instagram.py:57`
- Rate limit: sleeps 1s every 12 reels — `recon/scraper/instagram.py:169-170`
- Max reels per competitor: 50 (default) — `recon/scraper/instagram.py:95`
- Video download fallback: `requests.get(post.video_url)` with authenticated instagram session — `recon/scraper/instagram.py:203-219`

---

## Provider: yt-dlp (YouTube Scraper)

### Purpose
YouTube competitor video discovery and transcript extraction — no API key needed.

### Configuration
- **API Key:** None — uses the `yt-dlp` CLI tool (C library)
- **Base URLs:** Constructed by yt-dlp internally — `recon/scraper/youtube.py:44` and `skills/last30days/scripts/lib/youtube_yt.py:119`

### Endpoints Called
N/A — yt-dlp handles all YouTube API interactions internally

### Usage Locations
- `recon/scraper/youtube.py:26-115` — Channel video listing (Recon module)
- `recon/scraper/youtube.py:118-173` — Video downloading
- `skills/last30days/scripts/lib/youtube_yt.py:88-201` — YouTube search (last30days skill)
- `skills/last30days/scripts/lib/youtube_yt.py:226-291` — Transcript fetching via subtitles
- `skills/last30days/scripts/lib/youtube_yt.py:331-367` — Full search + transcribe pipeline

### Hardcoded Assumptions
- yt-dlp must be in PATH — `recon/scraper/youtube.py:111`, `skills/last30days/scripts/lib/youtube_yt.py:47`
- For channel videos: `--flat-playlist --dump-json --playlist-end N` — `recon/scraper/youtube.py:58-65`
- For downloading: `-f "bestaudio[ext=m4a]/bestaudio/best"` — `recon/scraper/youtube.py:144`
- For last30days search: `ytsearch{count}:{core_topic}` — `skills/last30days/scripts/lib/youtube_yt.py:119`
- For transcripts: `--write-auto-subs --sub-lang en --sub-format vtt` — `skills/last30days/scripts/lib/youtube_yt.py:237-243`
- Depth result counts: 10/20/40 — `skills/last30days/scripts/lib/youtube_yt.py:24-27`
- Transcript limits: 3/5/8 — `skills/last30days/scripts/lib/youtube_yt.py:30-33`
- Max transcript words: 500 — `skills/last30days/scripts/lib/youtube_yt.py:36`
- Parallel transcript workers: 5 — `skills/last30days/scripts/lib/youtube_yt.py:296`
- Hardcoded soft date filter: requires ≥3 items in range to discard old ones — `skills/last30days/scripts/lib/youtube_yt.py:191-196`

---

## Summary

### Total hardcoded providers: 12

| # | Provider | Category | Configurable Base URL? | Auth Method | SDK |
|---|---|---|---|---|---|
| 1 | **OpenAI** | LLM + Transcription + Search | No | Bearer token | `requests` raw HTTP |
| 2 | **Anthropic** | LLM | No | `x-api-key` header | `requests` raw HTTP |
| 3 | **Google Gemini** | LLM | No | API key (query param) | `requests` raw HTTP |
| 4 | **Ollama** | LLM (local) | No (localhost:11434) | None | `requests` raw HTTP |
| 5 | **xAI / Grok** | X Search | No | Bearer token | `urllib` via `http.py` |
| 6 | **OpenRouter / Sonar** | Web Search | No | Bearer token | `urllib` via `http.py` |
| 7 | **Brave Search** | Web Search | No | `X-Subscription-Token` | `urllib` via `http.py` |
| 8 | **Parallel AI** | Web Search | No | Bearer token | `urllib` via `http.py` |
| 9 | **Instagram Graph API** | Analytics | No (v21.0) | Query param token | `requests` raw HTTP |
| 10 | **YouTube Data + Analytics** | Analytics | No | API key + OAuth Bearer | `requests` raw HTTP |
| 11 | **Reddit JSON** | Social Discovery | No | None (User-Agent) | `urllib` via `http.py` |
| 12 | **Bird X (vendored)** | X Discovery | N/A (vendored .mjs) | X cookies/auth token | Node.js subprocess |

### Providers with configurable base URL: 0
Every provider has its base URL hardcoded — none are configurable via env var or config file.

### Providers fully hardcoded (no config at all): 12
All 12 providers have their endpoints, auth methods, request body structures, and response parsing logic hardcoded directly in Python files.

### Key Findings
1. **No abstraction layer** — Each provider is called directly with raw HTTP. The `http.py` utility (`skills/last30days/scripts/lib/http.py`) wraps `urllib.request` for some providers (OpenAI Reddit, xAI, OpenRouter, Brave, Parallel AI) but does not provide any API abstraction — it's just a retry+JSON wrapper.
2. **The recon LLM client** (`recon/skeleton_ripper/llm_client.py`) is the closest thing to an abstraction layer, with a `ProviderConfig` pattern that maps provider ID → base URL, API key env var, models, and a `chat()` method that dispatches to provider-specific `_call_*` methods. However, each provider still has its own hardcoded request body and response parsing.
3. **Web search has a priority chain**: Parallel AI > Brave > OpenRouter/Sonar Pro (in `skills/last30days/scripts/lib/env.py:103-116`) but the selection logic is duplicated in `get_web_search_source()`.
4. **All API base URLs are hardcoded strings** — no environment variable overrides exist for any endpoint URL.
5. **Auth methods are inconsistent**: Bearer token (`Authorization`), query parameter (`access_token`, `key=`), custom header (`x-api-key`, `X-Subscription-Token`), and no auth (Ollama, Reddit, Bird) — all hardcoded per-provider.

---

*API audit: 2026-07-09*