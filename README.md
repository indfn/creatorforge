<h1 align="center">CREATORFORGE</h1>

```
#    _________                        __              ___________                         
#    \_   ___ \_______   ____ _____ _/  |_  __________\_   _____/__________  ____   ____  
#    /    \  \/\_  __ \_/ __ \\__  \\   __\/  _ \_  __ \    __)/  _ \_  __ \/ ___\_/ __ \ 
#    \     \____|  | \/\  ___/ / __ \|  | (  <_> )  | \/     \(  <_> )  | \/ /_/  >  ___/ 
#     \______  /|__|    \___  >____  /__|  \____/|__|  \___  / \____/|__|  \___  / \___  >
#            \/             \/     \/                      \/             /_____/      \/ 
```

<p align="center">
  AI-powered video content creation suite.<br/>
  Finds winning topics, develops angles, generates hooks, learns from performance.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.1.0-3b82f6?style=flat-square" alt="Version" />
  <img src="https://img.shields.io/badge/license-MIT-3b82f6?style=flat-square" alt="License" />
  <img src="https://img.shields.io/badge/platform-OpenCode_|_Claude_Code-3b82f6?style=flat-square" alt="Platform" />
  <a href="https://start.ccstrategic.io/skool"><img src="https://img.shields.io/badge/community-Skool-3b82f6?style=flat-square" alt="Skool Community" /></a>
</p>

<br/>

```bash
git clone https://github.com/indfn/creatorforge.git
cd creatorforge
bash scripts/init-creatorforge.sh
```

<p align="center">Works on Mac, Windows (WSL), and Linux.</p>

<br/>

<p align="center">

</p>

<br/>

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/indfn/creatorforge.git
cd creatorforge
bash scripts/init-creatorforge.sh
```

### 2. Set up API keys

```bash
creatorforge doctor          # Check what's missing
```

Follow the interactive prompts, or manually create `.env`:

```bash
# Required
LLM_API_KEY=your-gemini-or-openai-key
GROQ_API_KEY=your-groq-key
YOUTUBE_API_KEY=your-youtube-data-api-key

# Optional (for Instagram)
INSTAGRAM_SESSION_ID=your-session-id

# Optional (for TTS)
TTS_PROVIDER=edge          # edge (free), google-cloud, or openai
```

### 3. Create a channel

```bash
# OpenCode: type /viral:onboard in the CLI
# Claude Code: type /viral:onboard in the CLI
```

This creates `channels/YourChannel/` with `brain.json` and `channel_config.json`.

### 4. Run the pipeline

```bash
# OpenCode: use the viral-pipeline subagent
# Claude Code: run commands sequentially
```

---

## The Pipeline

```
 DISCOVER ──> ANGLE ──> SCRIPT ──> PRODUCE ──> PUBLISH ──> ANALYZE
    ^                                                         |
    |                                                         |
    └─── feedback loop (brain evolves — LEARN) ───────────────┘
```

| Stage | What Happens |
|-------|-------------|
| **Discover** | Pull your competitors' winning content — see what got the most engagement, transcribe their videos, extract hook skeletons, and repurpose them in your voice. Currently supports YouTube + Instagram. |
| **Angle** | Apply Contrast Formula to turn raw topics into format-specific angles (longform, shortform, LinkedIn) |
| **Script** | Generate hooks (6 patterns), full scripts (longform/shortform), filming cards, PDF lead magnets |
| **Produce** | Build the video — TTS audio, stock visuals, character SVGs, HyperFrames render, multi-format output |
| **Publish** | Upload to YouTube with SEO metadata, thumbnail, scheduling, and playlist assignment |
| **Analyze** | Pull analytics (views, CTR, AVD, retention), extract winners, identify patterns |
| **Learn** | Evolve brain weights from performance data — the feedback loop |

---

## Usage by CLI Tool

### OpenCode

OpenCode auto-consumes `AGENTS.md` via the `viral-pipeline` subagent.

```bash
# Start OpenCode in the project directory
opencode

# The viral-pipeline subagent orchestrates the full workflow:
# 1. It reads AGENTS.md for the playbook
# 2. Runs each stage sequentially
# 3. Checks outputs before proceeding
```

**Manual commands (if needed):**

```bash
/viral:setup          # First-time platform setup
/viral:onboard        # Create/configure a channel
/viral:discover       # Run competitor discovery
/viral:angle          # Develop content angles
/viral:script         # Generate video script
/publish-video        # Upload to YouTube
/viral:analyze        # Collect performance data
/viral:update-brain   # Evolve brain weights
```

### Claude Code

Claude Code uses `/` commands defined in `.claude/commands/`.

```bash
# Start Claude Code in the project directory
claude

# Run the pipeline step by step:
/viral:onboard        # 1. Create a channel
/viral:discover       # 2. Find winning topics
/viral:angle          # 3. Develop angles
/viral:script         # 4. Generate script
# ... produce the video manually or via skills
/publish-video        # 5. Upload to YouTube
/viral:analyze        # 6. Collect analytics
/viral:update-brain   # 7. Evolve brain weights
```

**Health check:**

```bash
creatorforge doctor          # Verify all dependencies and API keys
```

---

## Commands

| Command | What It Does |
|---------|-------------|
| `creatorforge doctor` | Health check — verifies Python, Node, API keys, OAuth tokens, FFmpeg |
| `/viral:setup` | Platform connection wizard — dependency check, API config, verification |
| `/viral:onboard` | Interactive agent brain setup — ICP, pillars, platforms, competitors |
| `/viral:discover` | Topic discovery — competitor scrape, YouTube/Instagram keyword search |
| `/viral:angle` | Contrast Formula angle development — 5 angles per format |
| `/viral:script` | Interactive script generator — pick format → pick angle → hooks + full script |
| `/publish-video` | Upload rendered video to YouTube with SEO metadata |
| `/viral:analyze` | Multi-platform analytics + winner extraction + feedback loop |
| `/viral:update-brain` | Brain evolution protocol + insight aggregation |
| `/viral:status` | Check pipeline state and pending actions |

---

## Features

- **Agent brain** that evolves from your performance data
- **Competitor intelligence** — pull their winning content, see engagement rankings, transcribe videos, extract hook skeletons, repurpose in your voice
- **HookGenie engine** — 6 hook patterns with composite scoring
- **Format-based angles** — 5 angles per format (longform, shortform, LinkedIn) = 15 takes per topic
- **Video production** — TTS audio, stock visuals, character SVGs, HyperFrames render
- **PDF lead magnet generation** from any script
- **Discovery**: Competitor scraping (YouTube + Instagram) + keyword search — uses your brain's pillar keywords
- **Monetization coaching** baked into every output
- **Multi-tool support** — works with OpenCode, Claude Code, and other AI CLIs

---

## Architecture

```
CreatorForge/
├── AGENTS.md                 # Pipeline playbook for AI agents
├── .agents/                  # Canonical agent configs
│   ├── agents/               # Subagent prompts (viral-pipeline, hyperframe-renderer)
│   ├── commands/             # OpenCode command wrappers
│   ├── commands.claude/      # Claude Code commands (full prompts)
│   ├── docs/                 # Per-stage deep-dive docs
│   │   ├── discover.md
│   │   ├── angle.md
│   │   ├── script.md
│   │   ├── produce.md
│   │   ├── publish.md
│   │   ├── analyze.md
│   │   └── learn.md
│   └── skills/               # Shared skills (hyperframes, media-use, etc.)
├── .claude/                  # Claude Code symlinks → .agents/
├── .opencode/                # OpenCode config + symlinks → .agents/
├── channels/                 # Per-channel data
│   └── {Name}/
│       ├── brain.json        # Agent brain (weights, topics, angles)
│       ├── channel_config.json
│       └── active_production/  # Current video being produced
├── agent_core/               # Python package (pipeline logic)
├── scripts/                  # Setup + utility scripts
├── schemas/                  # JSON Schema contracts
└── recon/                    # Competitor analysis module
```

---

## Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10+ | Core pipeline language |
| Node.js | 18+ | HyperFrames rendering |
| FFmpeg | Latest | Video assembly |
| Playwright | Latest | Browser-based rendering (`npx playwright install chromium`) |

**API keys** (in `.env`):

| Key | Required | Used For |
|-----|----------|----------|
| `LLM_API_KEY` | Yes | Script generation, angle development |
| `GROQ_API_KEY` | Yes | Transcription (free tier) |
| `YOUTUBE_API_KEY` | Yes | Competitor discovery, publishing |
| `INSTAGRAM_SESSION_ID` | Optional | Instagram competitor discovery |
| `PEXELS_API_KEY` | Optional | Stock video/images |
| `PIXABAY_API_KEY` | Optional | Stock video/images (fallback) |

See [SETUP.md](SETUP.md) for detailed installation and platform connection guides.

---

## Agent Documentation

The pipeline is fully documented for autonomous AI agent use:

- **`AGENTS.md`** — Root-level playbook: prerequisites, 7-stage workflow, manual operations
- **`.agents/docs/`** — Per-stage deep-dives with input/output contracts, commands, error recovery
- **`.agents/agents/viral-pipeline.md`** — Subagent prompt that orchestrates the full pipeline

Any AI CLI (OpenCode, Claude Code, Codex) can read these files and autonomously run the pipeline.

---

## Tool Compatibility

This documentation is designed for any agentic CLI:
- **OpenCode** auto-consumes `AGENTS.md` at the project root — the `viral-pipeline` subagent references it directly.
- **Claude Code** users should read `AGENTS.md` for the pipeline overview and `.agents/docs/` for per-stage deep-dives; existing `.claude/commands/` wrappers remain available.
- **Codex and other CLIs** can reference `AGENTS.md` as the canonical pipeline guide. All commands use `{name}` placeholder syntax for channel variables.

---

## Troubleshooting

```bash
# Check system health
creatorforge doctor

# Common issues:
# - "LLM_API_KEY not set" → Add to .env (see Requirements above)
# - "No channel found" → Run /viral:onboard first
# - "FFmpeg not found" → Install: apt install ffmpeg / brew install ffmpeg
# - "Playwright browsers missing" → Run: npx playwright install chromium
# - "YouTube quota exceeded" → Wait 24h or request quota extension
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT — see [LICENSE](LICENSE).

---

<p align="center">
  Built by <a href="https://ccstrategic.io">Charles Dove</a> · <a href="https://youtube.com/@charlieautomates">YouTube</a> · <a href="https://start.ccstrategic.io/skool">Skool Community</a>
</p>
