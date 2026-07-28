# Contributing to CreatorForge

Thanks for your interest in contributing. This project is an AI-powered content creation suite — contributions are typically `.md` command/skill files, Python scripts, or bash scripts.

---

## Reporting Bugs

Open a [GitHub Issue](https://github.com/indfn/creatorforge/issues) with:

- Which command you ran (e.g., `/viral:discover`, `viral-discover --channel {name}`)
- What you expected to happen
- What actually happened
- Your OS (macOS, Linux, Windows/WSL)
- Python and Node.js versions
- Output of `creatorforge doctor`

---

## Suggesting Features

Open a GitHub Issue with the `enhancement` label. Describe:

- What problem you're solving
- How you'd expect it to work
- Which command(s) it would affect

---

## Submitting Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests: `python3 -m pytest`
5. Run health check: `creatorforge doctor`
6. Commit with a clear message describing what changed and why
7. Push to your fork and open a PR against `main`

### Code Style

- **Bash scripts**: Use `set -euo pipefail` at the top. Quote variables. Use `#!/usr/bin/env bash`.
- **Python**: Follow PEP 8. Use type hints where practical.
- **Agent commands** (`.md` files): Follow the existing template structure. Include frontmatter with `description` field.
- **Schemas**: JSON Schema draft-07. Include `description` fields on properties.

### What to Avoid

- Don't add external database dependencies beyond SQLite (already in use)
- Don't add browser automation (API/CLI only)
- Don't modify `data/cta-templates.json` structure without updating dependent commands
- Don't commit `.env` files, API keys, or OAuth tokens
- Don't commit `channels/*/brain.json` (user-specific data)

---

## Project Structure

See [README.md](README.md#architecture) for the full directory layout. Key areas:

- `.agents/commands/` — OpenCode command wrappers
- `.agents/commands.claude/` — Claude Code commands (full prompts)
- `.agents/docs/` — Per-stage pipeline documentation
- `.agents/skills/` — Shared skills (hyperframes, media-use, etc.)
- `agent_core/` — Python package (pipeline logic)
- `schemas/` — Data contracts (changes here affect all commands)
- `scripts/` — Setup and utility scripts
- `channels/` — Per-channel data (brain.json, configs, production output)

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
