# Produce

## Purpose

Transform scripts into a finished video through three sub-steps: generate per-scene audio via TTS, source visual assets (stock footage, character SVGs, SFX), and render the final video with scene assembly, subtitles, and multi-format output.

## Input Contract

- Per-scene script files at `channels/{name}/active_production/scene_*_script.txt`
- Master script JSON at `channels/{name}/active_production/script.json`
- Channel asset library populated (consistent assets exist)
- API keys for TTS provider and stock media providers configured
- HyperFrames CLI installed and available (`npx hyperframes`)

## Commands

### Sub-step A: Audio

Generate per-scene TTS audio with word-level alignment and subtitles.

- **TTS generation:** No single command — executor invokes the TTS provider chain (custom TTS → Google Cloud → Edge TTS) via `agent_core.audio.tts`. Groq Whisper API performs force alignment for word-level timestamps.
- **Subtitle output:** Per-scene SRT/VTT files generated alongside audio.
- **Output location:** `channels/{name}/active_production/audio/scene_XX_audio.wav` and `scene_XX_subtitles.srt`
- **Recovery:** Check TTS API key and quota; verify Groq API key for alignment; confirm scene scripts are non-empty

### Sub-step B: Visuals

Source visual assets for each scene: B-roll footage, images, character SVGs, and sound effects.

- **Stock media sourcing:** Uses Pexels (primary) → Pixabay (fallback) for video/images; Freesound for SFX. Invoked through `agent_core.assets` providers.
- **Character SVGs:** Resolved through `agent_core.assets.CharacterResolver` with channel-specific overrides.
- **Wikimedia Commons:** Free public-domain/CC images with British Library vintage illustration preference.
- **Output location:** Temp assets at `channels/{name}/active_production/assets/` (cleaned up post-publish); consistent assets at `assets/consistent/`
- **Recovery:** Verify stock API keys and quota; check network connectivity; asset cache is SQLite-backed with TTL — stale caches auto-refresh

### Sub-step C: Render

Assemble audio, visuals, and subtitles into the final video.

- **HyperFrames composition:** Per-scene HTML blueprints with GSAP timelines (`data-*` timing attributes). See `.agents/skills/hyperframes-core/` for contract details.
- **Scene rendering:** Playwright captures HyperFrames composition → FFmpeg converts to scene clip MP4.
- **Assembly:** Scene clips joined with crossfade transitions; subtitles overlaid; multi-format output (16:9, 9:16, 1:1).
- **Output:** `channels/{name}/active_production/render/final_video.mp4` (primary 16:9; 9:16 and 1:1 variants also generated)
- **Recovery:** Verify audio files exist per scene; check FFmpeg is installed; verify Playwright browsers are installed; check disk space for intermediate frames

## Output Artifacts

- `channels/{name}/active_production/render/final_video.mp4` — Primary rendered video (16:9)
- `channels/{name}/active_production/render/final_video_9x16.mp4` — Vertical variant (9:16)
- `channels/{name}/active_production/render/final_video_1x1.mp4` — Square variant (1:1)
- `channels/{name}/active_production/audio/scene_XX_audio.wav` — Per-scene audio (temp, cleaned up post-publish)
- `channels/{name}/active_production/audio/scene_XX_subtitles.srt` — Per-scene subtitle tracks (temp, cleaned up)
- `channels/{name}/active_production/assets/` — Temp visual assets (cleaned up)

## Error Recovery

- Sub-step A (Audio): Confirm TTS provider and Groq API keys; verify scene scripts parse correctly
- Sub-step B (Visuals): Check stock API rate limits; verify cached assets are not corrupted
- Sub-step C (Render): Check FFmpeg logs for codec errors; ensure Playwright browsers installed (`npx playwright install chromium`); verify adequate disk space (each scene HD frame ≈ 6MB)
- General: Run `creatorforge doctor` to validate environment; check channel disk quota

## Manual Only Ops

None for the produce stage — all production steps are automated through the pipeline.

## Related

- [AGENTS.md](../AGENTS.md) — Pipeline overview
- [.agents/skills/hyperframes-core/](../skills/hyperframes-core/) — HyperFrames composition contract
- [.agents/skills/hyperframes-animation/](../skills/hyperframes-animation/) — Animation rules and scene blueprints
- [.agents/skills/hyperframes-cli/](../skills/hyperframes-cli/) — CLI dev loop for preview and render
- [.agents/skills/media-use/](../skills/media-use/) — Media asset resolution
