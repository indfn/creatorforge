# Feature Landscape: AI Video Production / YouTube Publishing

**Domain:** AI Content Creation Pipeline
**Researched:** 2026-07-10
**Confidence:** HIGH

## Table Stakes

Features users expect. Missing = pipeline feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| YouTube OAuth 2.0 token lifecycle | Can't upload without auth | Medium | offline access, auto-refresh, per-channel tokens |
| Resumable video upload | Must handle network failures | Medium | HTTP 5xx retry, chunk size 256KB multiples |
| Video metadata (title, desc, tags) | SEO optimization | Low | LLM-generated SEO metadata is standard |
| Privacy status control | Public/private/unlisted/scheduled | Low | publishAt requires privacyStatus=private |
| Basic analytics collection | Need performance data | Medium | min 24h delay, batch by video ID |
| TTS voiceover generation | Required for faceless content | Low | Multi-provider fallback (Google Cloud → Edge → pyttsx3) |
| B-roll / image asset sourcing | Visual content needs footage | Medium | Pexels/Pixabay API, rate limits, caching |
| Video rendering (FFmpeg) | Must produce final MP4 | Medium | Single-pass filter_complex, not per-scene |
| Per-channel configuration | Multi-channel management | Low | Currently exists in `channels/{Name}/channel_config.json` |
| Agent brain (ICP, pillars) | Content strategy foundation | Low | Currently exists as agent-brain.json |

## Differentiators

Features that set CreatorForge apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Self-improving brain (analytics → weight update) | Content strategy evolves automatically | High | Core differentiator. Algorithm design needed for weight transformation. |
| Multi-channel unified dashboard | Manage all channels from one tool | Medium | Requires cross-channel aggregation |
| Automated scheduling (peak time) | Maximize reach without manual planning | Medium | Uses channel analytics to determine best publish time |
| Quality gates with dry-pass graduation | Prevents bad content without blocking | Medium | Schema validation + domain checks + graduated enforcement |
| Checkpoint-based crash recovery | Never re-do work on failure | Medium | Typed artifacts between all stages |
| Parallel audio+visual production | 2x faster than serial pipeline | Low-Medium | no data dependency between audio and visual stages |
| Quota-aware upload scheduling | Graceful degradation on quota | Low | QuotaBudget manager defers uploads to next day |
| Force-aligned captions (word-level) | Professional subtitle sync | High | Requires reliable alignment — may need cloud API |
| Multi-format output (9:16, 16:9, 1:1) | Publish to Shorts + long-form + Instagram | Medium | Configurable render config; different crops for each |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Custom video player UI | Not a consumer product | Let YouTube handle playback |
| Canvas-based render engine | FFmpeg is battle-tested and faster | Use FFmpeg filter graphs |
| Real-time analytics dashboard | 24h minimum delay makes "real-time" meaningless | Scheduled daily/weekly reports |
| Instagram/TikTok native upload | Scope creep; doubles auth complexity | Focus on YouTube first; add platforms later |
| Multi-language translation | Niche requirement, high complexity | Generate in primary language only |
| Client-side video editing | Processing power is server-side | Keep all compute in Python backend |

## Feature Dependencies

```
OAuth 2.0 Token Lifecycle → Resumable Upload (auth required for upload)
Resumable Upload → Video Render (need rendered file before upload)
Video Render → Visual Assets + Audio + Script (all inputs needed)
Analytics Collection → Upload (need published video before analytics)
Analytics Collection → Brain Updater (metrics before update)
Brain Updater → Scoring Engine (updated weights before next score)
Scoring Engine → Agent Brain (needs brain to read)
Quota Budget → YouTube API Calls (check before any API operation)
Checkpoints → All Stages (checkpoints wrap every stage)
Quality Gates → All Stages (gates validate at stage boundaries)
```

## MVP Recommendation

**Phase 1 (Distribution):**
1. OAuth 2.0 token lifecycle with offline access
2. Resumable upload with exponential backoff
3. QuotaBudget manager with persistent tracking
4. SEO metadata generation (LLM-based)
5. Scheduling support (publishAt + privacyStatus)

**Phase 2 (Analytics):**
1. 24h-delayed analytics collection
2. Cross-channel aggregation
3. Brain weight updater (simple version: multiply weights by performance ratio)
4. Scoring engine integration (new topics use updated weights)

**Phase 3 (Visual/Render):**
1. Pexels/Pixabay asset scraping with caching
2. Single-pass FFmpeg compositor
3. Force alignment for captions
4. Multi-format output support

**Defer:**
- Real-time dashboard: Not useful with 24h analytics delay
- Multi-platform publishing: YouTube-only until OAuth is stable
- Advanced brain algorithms: Start with simple weight multiplication; evolve later

## Sources

- Current CreatorForge codebase: CONCERNS.md (70% stubs, missing feature gaps)
- Showrunner architecture: typed artifacts as contracts between agents
- montage-ai: multi-provider TTS fallback chain pattern
- OpenMontage: quality gate dry-pass/enforcement graduation model
- 4-Plane Architecture: GTM goals as first-class state, human attention as architectural concern
- Leanboat self-improving engine: sensor → policy → tool → quality → learning layers
