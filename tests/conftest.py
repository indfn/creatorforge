"""
Shared pytest fixtures for all CreatorForge test modules.

Fixture inventory:
    brain_data              — Returns a standard agent-brain dict for testing
    tmp_brain_file          — Writes brain_data to a temporary JSON file, returns Path
    tmp_credentials_dir     — Returns a temp ~/.creatorforge/ directory with 0700 perms
    sample_skeleton         — Returns a standard skeleton/competitor-analysis dict
    sample_transcript       — Returns a minimal valid transcript string
    mock_agent_core_packages — Patches agent_core logger to prevent file I/O during tests
    isolated_credentials    — Patches agent_core.recon.config paths to temp locations

All fixtures use ``tmp_path`` (built-in pytest fixture) for temp directories
and ``monkeypatch`` for environment isolation. No fixtures have ``autouse=True``
— tests must explicitly request what they need.

No module-level imports from ``agent_core`` to prevent import-time side effects.
"""

import json

import pytest


@pytest.fixture(scope="function")
def brain_data():
    """Return a standard agent-brain dict for testing."""
    return {
        "icp": {
            "pain_points": [
                "scaling revenue without adding headcount",
                "managing remote team productivity",
                "automating repetitive business processes",
            ],
            "goals": ["grow revenue 3x", "automate operations"],
            "segments": ["founders", "startups"],
        },
        "pillars": [
            {"name": "AI Automation", "keywords": ["automation", "AI", "workflow"]},
            {
                "name": "Growth Hacking",
                "keywords": ["growth", "viral", "traffic", "hacking"],
            },
        ],
        "learning_weights": {
            "icp_relevance": 1.0,
            "timeliness": 1.0,
            "content_gap": 1.0,
            "proof_potential": 1.0,
        },
        "competitors": [
            {
                "name": "Test Creator",
                "platform": "instagram",
                "handle": "@testcreator",
                "why_watch": "great content",
            }
        ],
    }


@pytest.fixture(scope="function")
def tmp_brain_file(brain_data, tmp_path):
    """Write brain_data to a temporary JSON file and return the Path."""
    brain_path = tmp_path / "agent-brain.json"
    brain_path.write_text(json.dumps(brain_data, indent=2))
    return brain_path


@pytest.fixture(scope="function")
def tmp_credentials_dir(tmp_path):
    """Return a temp ~/.creatorforge/ directory with 0700 perms."""
    creds_dir = tmp_path / ".creatorforge"
    creds_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    return creds_dir


@pytest.fixture(scope="function")
def sample_skeleton():
    """Return a standard skeleton / competitor-analysis dict."""
    return {
        "creator_username": "testcreator",
        "platform": "instagram",
        "views": 75000,
        "likes": 5000,
        "hook": "This technique changed everything for my workflow",
        "value": "In this video I show you how to build a viral channel step by step with automation",
        "hook_technique": "curiosity_gap",
        "value_structure": "step_by_step_tutorial",
        "url": "https://instagram.com/p/abc123/",
        "video_url": "https://instagram.com/p/abc123/video/",
        "transcript": "This technique changed everything for my workflow. In this video I show you how to build a viral channel step by step with automation.",
        "extracted_at": "2026-07-12T00:00:00",
        "extraction_model": "custom/gpt-4o-mini",
    }


@pytest.fixture(scope="function")
def sample_transcript():
    """Return a minimal valid transcript string (>10 words)."""
    return (
        "This technique changed everything for my workflow and helped me grow "
        "my channel to 100k subscribers in just three months."
    )


@pytest.fixture(scope="function")
def mock_agent_core_packages(monkeypatch):
    """Patch agent_core.recon.utils.logger.get_logger to return a no-op logger.

    Prevents file I/O during tests that import agent_core modules.
    """
    import logging

    noop_logger = logging.getLogger("test-noop")
    noop_logger.addHandler(logging.NullHandler())

    monkeypatch.setattr(
        "agent_core.recon.utils.logger.get_logger", lambda name: noop_logger
    )


@pytest.fixture(scope="function")
def isolated_credentials(monkeypatch, tmp_path):
    """Patch agent_core.recon.config paths to point to temp locations.

    Ensures credential tests never touch real ~/.creatorforge/ or agent-brain.json.
    """
    # Import inside fixture body to prevent module-level import side effects
    import agent_core.recon.config as config

    creds_dir = tmp_path / ".creatorforge"
    creds_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    monkeypatch.setattr(config, "CREDENTIALS_KEY_DIR", creds_dir)
    monkeypatch.setattr(
        config,
        "CREDENTIALS_KEY_FILE",
        creds_dir / "credentials.key",
    )
    monkeypatch.setattr(
        config,
        "CREDENTIALS_FILE",
        tmp_path / ".credentials",
    )
    monkeypatch.setattr(
        config,
        "BRAIN_FILE",
        tmp_path / "agent-brain.json",
    )
