# CreatorForge Agent Pipeline

End-to-end pipeline for AI-powered video content creation — from competitor discovery through publishing and learning.

## Prerequisites

- Active channel directory: `channels/{Name}/` with `channel_config.json`
- Required API keys in `.env` (LLM, Groq, YouTube, etc.)
- Run `creatorforge doctor` to verify setup

## Pipeline Overview

1. **Discover** — Find winning topics via competitor analysis and keyword research
2. **Angle** — Develop content angles from discovered topics
3. **Script** — Generate hook and full video script
4. **Produce** — Build the video (Audio → Visuals → Render)
5. **Publish** — Upload to YouTube with metadata and scheduling
6. **Analyze** — Collect performance data and engagement metrics
7. **Learn** — Evolve brain weights from performance data

## Stage Details

### 1. Discover

- **Goal:** Find winning topics via competitor analysis and keyword research scoped to the active channel
- **Command:** `viral-discover --channel {name}`
- **Input:** Channel `channels/{name}/brain.json` with weight preferences; API keys for YouTube/Instagram
- **Output:** Discovered topics scored and ranked in `channels/{name}/brain.json`
- **Recovery:** Verify API keys are set and quota not exhausted; run `creatorforge doctor`

### 2. Angle

- **Goal:** Develop content angles from discovered topics using channel-specific brain weights
- **Command:** `viral-angle --channel {name}`
- **Input:** `channels/{name}/brain.json` with discovered topics from Stage 1
- **Output:** Content angles with hook concepts in `channels/{name}/brain.json`
- **Recovery:** Ensure Stage 1 completed first; check `channels/{name}/brain.json` has topics

### 3. Script

- **Goal:** Generate hook and full video script from the selected angle
- **Command:** `viral-script --channel {name}`
- **Input:** Selected angle from Stage 2
- **Output:** Script files at `channels/{name}/active_production/scene_*_script.txt`
- **Recovery:** Verify LLM API key is set; check script output directory exists

### 4. Produce

- **Goal:** Build the video from script — audio, visuals, and final render
- **Command:** No single command — three sub-steps:
  - Audio: TTS pipeline generates per-scene audio from scene scripts
  - Visuals: Stock API sourcing (Pexels/Pixabay) + character SVG resolution
  - Render: HyperFrames composition → Playwright capture → FFmpeg assembly
- **Input:** Script files from Stage 3; channel asset library
- **Output:** `channels/{name}/active_production/render/final_video.mp4` (primary 16:9; 9:16 and 1:1 variants also generated)
- **Recovery:** Check each sub-step independently — verify audio files exist, visual cache is populated, render logs for FFmpeg errors

### 5. Publish

- **Goal:** Upload rendered video to YouTube with SEO metadata and optional scheduling
- **Command:** `publish-video --channel {name} [--schedule HH:MM]`
- **Input:** Rendered video at `channels/{name}/active_production/render/final_video.mp4`; `channel_config.json`
- **Output:** Published YouTube video; `channels/{name}/brain.json` updated with publish timestamp
- **Recovery:** Verify render output exists; check OAuth token validity; confirm YouTube quota is available

### 6. Analyze

- **Goal:** Collect video performance data (views, CTR, AVD, retention) after publishing
- **Command:** `viral-analyze --channel {name}`
- **Input:** Published video ID (stored in `brain.json` after Stage 5)
- **Output:** Analytics entries persisted to channel data directory
- **Recovery:** Analytics requires 24h (basic) / 72h (deep) after publish — check video age

### 7. Learn

- **Goal:** Evolve brain learning weights from real performance data
- **Command:** `viral-update-brain --channel {name}`
- **Input:** Analytics data from Stage 6; minimum 3 videos per content pillar
- **Output:** Updated `channels/{name}/brain.json` with refined weights
- **Recovery:** Not enough data yet — need at least 3 videos per pillar; continue publishing

## Manual Operations (YouTube Studio)

- **End screens & Cards:** Add via YouTube Studio → Content → video → Editor. Not available via API.
- **Thumbnail A/B Testing:** YouTube Studio → Content → Test & Compare. API supports thumbnail upload but not A/B experiments.
- **Community Posts:** Create manually via YouTube Studio → Community. No API for community posts.

## Next Steps

- Run each stage in order, checking outputs before proceeding
- For stage details, see `.agents/docs/{stage}.md`
- Run `creatorforge doctor` anytime to verify system health
