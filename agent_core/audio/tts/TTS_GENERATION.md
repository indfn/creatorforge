# TTS Generation

The CreatorForge audio pipeline generates per-scene voiceover audio through a
4-provider fallback chain. Each scene's `_script.txt` is synthesized to a WAV
file, then force-aligned for word-level timestamps.

---

## Provider Chain

TTS providers are tried in order. The first to return a result wins.

| Order | Provider | Auth | When it's used | Free? |
|-------|----------|------|----------------|-------|
| 1 | `CustomTTSProvider` | `TTS_API_KEY` + `TTS_PROXY_URL` | Primary — calls Gemini Flash TTS proxy | Depends on proxy backend |
| 2 | `GeminiTTSProvider` | `GEMINI_API_KEY` | Fallback if custom fails | Yes (60 req/min free tier) |
| 3 | `GoogleCloudTTSProvider` | ADC (`GOOGLE_APPLICATION_CREDENTIALS`) | Fallback if gemini fails | 1M chars/mo free, then paid |
| 4 | `EdgeTTSProvider` | none | Final fallback — always works | Yes, free |

Configure the order or disable providers per channel in `channel_config.json`:

```json
{
  "production": {
    "tts": {
      "provider": "custom",
      "fallback_chain": ["custom", "gemini", "edge"],
      "characters": { ... }
    }
  }
}
```

---

## Per-Scene Generation (Audio Pipeline)

The audio pipeline (`agent_core/audio/pipeline.py`) handles per-scene generation
with checkpoint resumption:

1. **Read script** — each scene has `scene_XX_script.txt` with optional emotion
   tags (e.g. `[curiosity]`, `[laughs]`)
2. **Load voice config** — reads `channel_config.json` → `production.tts.characters`
   to get voice, style, pace, accent, profile
3. **Synthesize** — passes to fallback chain; writes `scene_XX_audio.wav`
4. **Force align** — calls `force_align_scene()` via Groq Whisper API (or local
   `faster-whisper`), rewrites `scene_XX_script.txt` with word-level timestamps
5. **Generate subtitles** — creates `scene_XX_subtitles.srt` / `.vtt`

```bash
# Full pipeline (with per-scene checkpoint resumption)
python -m agent_core.audio.pipeline --channel ChannelA --production-id prod_001
```

---

## Standalone CLI

For single-file TTS without the full pipeline:

```bash
# Entry point registered in pyproject.toml
creatorforge-tts --script_path script.txt --output_path output/audio

# Or directly via module
python -m agent_core.audio.tts.generate --script_path script.txt --output_path output/audio

# All performance knobs available
creatorforge-tts \
  --script_path channels/ChannelA/active_production/scene_01_script.txt \
  --output_path channels/ChannelA/active_production/scene_01_audio \
  --voice Zephyr --style "Vocal Smile" --pace Natural \
  --accent "American (Gen)" --profile "Warm and educational"
```

---

## Performance Direction Parameters (Custom / Gemini Provider)

The custom and gemini providers use a **directed prompt** to tell the model HOW
to perform the narration. These 7 parameters combine into a structured prompt
that drives vocal delivery — they are NOT just metadata.

### How the prompt is built

```python
build_directed_prompt(
    script_text=script_text,
    profile="Warm and educational",
    scene="Inside a medieval cathedral, echoes and footsteps on stone",
    style="Vocal Smile",
    pace="Natural",
    accent="British (RP)",
    sample_context="Explaining Gothic architecture to a general audience",
)
```

This produces:

```
1. Synthesize speech for the performance defined below. The profile, scene,
   performance notes, and context are direction only. Do NOT speak them.
2. Speak ONLY the lines under #### TRANSCRIPT.

# AUDIO PROFILE
Warm and educational

### SCENE
Inside a medieval cathedral, echoes and footsteps on stone

### PERFORMANCE
Style: Vocal Smile
Pace: Natural
Accent: British (RP)

### CONTEXT
Explaining Gothic architecture to a general audience

#### TRANSCRIPT
[the actual narration text]
```

### Per-parameter guidance

| Parameter | Source | How to set per scene |
|-----------|--------|----------------------|
| `voice` | Config → `characters.{name}.voice` | Static per character |
| `profile` | Config → `characters.{name}.profile` | Static per character — describes the narrator persona |
| `style` | Config → `characters.{name}.style` | Static per character (e.g. Vocal Smile, Newscaster) |
| `pace` | Config → `characters.{name}.pace` | Static per character |
| `accent` | Config → `characters.{name}.accent` | Static per character |
| `scene` | **Derived per scene** | Describe the scene's physical environment, mood, and context that would influence vocal delivery. Examples: "A vast library with towering bookshelves, whispers echoing" or "An intense debate stage under harsh lights with crowd murmuring" |
| `context` | **Derived per scene** | 1-2 sentence summary of what the scene is explaining and the intended audience reaction. Examples: "Explaining the science behind black holes to a curious but non-expert audience, aiming for wonder" or "Delivering a punchy marketing hook for a productivity app, aiming for urgency" |

**Rule:** `scene` and `context` must be read from the scene content, narration
tone, and visual directives — never from static config. The agent should
compose them fresh for each scene based on what the narration is about.

### Automation pattern

```python
import json, subprocess
from pathlib import Path

from agent_core.audio.tts.generate import synthesize
from agent_core.audio.tts.fallback_chain import FallbackChain

# Option A: use synthesize() directly (custom/gemini only)
audio_bytes, mime, ext = synthesize(
    script_text="Your narration text here",
    voice="Zephyr",
    style="Vocal Smile",
    pace="Natural",
    accent="American (Gen)",
    profile="Warm and educational",
    scene="describe the physical scene per-scene",
    context="describe the narrative context per-scene",
)

# Option B: use the fallback chain (tries all 4 providers)
chain = FallbackChain()
result = chain.generate(
    text="Your narration text here",
    voice_config={
        "voice": "Zephyr",
        "style": "Vocal Smile",
        "pace": "Natural",
        "accent": "American (Gen)",
        "profile": "Warm and educational",
        "scene": "per-scene scene description",
        "context": "per-scene context description",
    },
)
if result:
    # result.audio_path — path to generated WAV
    # result.duration_seconds — duration in seconds
    pass

# Option C: per-scene via the full audio pipeline
subprocess.run([
    "python", "-m", "agent_core.audio.pipeline",
    "--channel", "ChannelA",
    "--production-id", "prod_001",
], check=True)
```

### Channel config (`channels/{Name}/channel_config.json`)

```json
{
  "production": {
    "tts": {
      "provider": "custom",
      "characters": {
        "main": {
          "voice": "Zephyr",
          "style": "Vocal Smile",
          "pace": "Natural",
          "accent": "American (Gen)",
          "profile": "Warm and educational"
        }
      }
    }
  }
}
```

- `provider` — the active provider key (matches a key in the fallback chain)
- `fallback_chain` — optional; defaults to `["custom", "gemini", "google_cloud", "edge"]`
- `characters` — map of character name → voice config. Use `main` unless a scene
  specifies a different `"character"` field
- `scene` and `context` are **not** stored in config — the agent derives them per
  scene at generation time. See "Performance Direction Parameters" below for
  guidance on composing good values.

### Emotion Tags (injected into script text)

```
[admiration]  [adoration]   [aggression]   [agitation]
[amusement]   [anger]       [annoyance]    [awe]
[confusion]   [curiosity]   [determination][enthusiasm]
[excitement]  [frustration] [hope]         [interest]
[laughs]      [negative]    [nervousness]  [neutral]
[positive]    [tension]     [whispers]
```

Only these tags are supported. Place them directly before the word or sentence.

### Voices (Gemini Flash TTS)

Built-in prebuilt voices for the custom/gemini providers:

`Zephyr` (default), `Achernar`, `Achird`, `Algenib`, `Algieba`, `Alnilam`,
`Aoede`, `Autonoe`, `Callirrhoe`, `Charon`, `Despina`, `Enceladus`, `Erinome`,
`Fenrir`, `Gacrux`, `Iapetus`, `Kore`, `Laomedeia`, `Leda`, `Orus`, `Puck`,
`Pulcherrima`, `Rasalgethi`, `Sadachbia`, `Sadaltager`, `Schedar`, `Sulafat`,
`Umbriel`, `Vindemiatrix`, `Zubenelgenubi`

### Performance Styles

`Vocal Smile`, `Newscaster`, `Whisper`, `Empathetic`, `Promo/Hype`, `Deadpan`

### Pacing

`Natural`, `Rapid Fire`, `The Drift`, `Staccato`

### Accents

`Neutral`, `American (Gen)`, `American (Valley)`, `American (South)`,
`British (RP)`, `British (Brixton)`, `Transatlantic`, `Australian`

---

## Key Files

| File | Purpose |
|------|---------|
| `agent_core/audio/tts/generate.py` | Standalone CLI + importable `synthesize()` function |
| `agent_core/audio/tts/custom_provider.py` | `CustomTTSProvider` — calls `synthesize()` directly |
| `agent_core/audio/tts/gemini_provider.py` | `GeminiTTSProvider` — Google genai SDK |
| `agent_core/audio/tts/google_cloud_provider.py` | `GoogleCloudTTSProvider` — GCP Text-to-Speech |
| `agent_core/audio/tts/edge_provider.py` | `EdgeTTSProvider` — `edge-tts` subprocess |
| `agent_core/audio/tts/fallback_chain.py` | `FallbackChain` orchestrator |
| `agent_core/audio/tts/base.py` | `BaseTTSProvider` ABC |
| `agent_core/audio/pipeline.py` | Per-scene audio pipeline with checkpoint resumption |
| `agent_core/audio/alignment/aligner.py` | Force alignment (Groq / faster-whisper) |
