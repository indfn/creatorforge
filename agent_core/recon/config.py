"""
Recon — Configuration module.
Reads competitor list from agent-brain.json, manages credentials and API keys.
Credentials loaded from .env (project root). Legacy .credentials file as fallback.
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass


PIPELINE_DIR = Path(__file__).parent.parent
DATA_DIR = PIPELINE_DIR / "data"
RECON_DATA_DIR = DATA_DIR / "recon"
CREDENTIALS_FILE = RECON_DATA_DIR / ".credentials"
BRAIN_FILE = DATA_DIR / "agent-brain.json"
ENV_FILE = PIPELINE_DIR / ".env"


def _load_env_file(path: Path) -> Dict[str, str]:
    """Load key=value pairs from a .env file."""
    env = {}
    if not path.exists():
        return env
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip()
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                if key:
                    # Strip value after # (inline comment), but only if space before #
                    comment_pos = value.find(' #')
                    if comment_pos > 0:
                        value = value[:comment_pos].strip()
                    env[key] = value
    return env


@dataclass
class Competitor:
    """A competitor from the agent brain."""
    name: str
    platform: str
    handle: str
    why_watch: str


@dataclass
class ReconConfig:
    """Full configuration for a recon session."""
    competitors: List[Competitor]
    ig_username: Optional[str] = None
    ig_password: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_provider: str = "custom"
    transcribe_api_key: Optional[str] = None
    transcribe_base_url: str = "https://api.openai.com/v1"
    transcribe_model: str = "whisper-1"
    transcribe_provider: str = "openai"
    whisper_model: str = "small.en"


def load_competitors() -> List[Competitor]:
    """Load competitor list from agent-brain.json."""
    if not BRAIN_FILE.exists():
        return []

    with open(BRAIN_FILE, 'r', encoding='utf-8') as f:
        brain = json.load(f)

    raw = brain.get("competitors", [])
    competitors = []
    for c in raw:
        competitors.append(Competitor(
            name=c.get("name", ""),
            platform=c.get("platform", "").lower(),
            handle=c.get("handle", ""),
            why_watch=c.get("why_watch", ""),
        ))

    return competitors


def load_credentials() -> Dict[str, str]:
    """
    Load credentials from .env file (project root) with .credentials fallback.
    Priority: environment vars > .env file > .credentials file.
    """
    creds = {}

    # Load .env from project root
    env_vars = _load_env_file(ENV_FILE)

    # Load .credentials as fallback
    if CREDENTIALS_FILE.exists():
        with open(CREDENTIALS_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    if key.strip() not in creds:
                        creds[key.strip()] = value.strip()

    # Override with .env file values
    creds.update(env_vars)

    # Override with actual environment variables (highest priority)
    env_map = {
        "IG_USERNAME": "ig_username",
        "IG_PASSWORD": "ig_password",
        "LLM_API_KEY": "llm_api_key",
        "TRANSCRIBE_API_KEY": "transcribe_api_key",
        "OPENAI_API_KEY": "openai_api_key",
        "LLM_BASE_URL": "llm_base_url",
        "LLM_MODEL": "llm_model",
        "TRANSCRIBE_BASE_URL": "transcribe_base_url",
        "TRANSCRIBE_MODEL": "transcribe_model",
        "TRANSCRIBE_PROVIDER": "transcribe_provider",
        "WHISPER_MODEL": "whisper_model",
    }

    for env_var, cred_key in env_map.items():
        val = os.environ.get(env_var)
        if val:
            creds[cred_key] = val

    return creds


def save_credentials(creds: Dict[str, str]):
    """Save credentials to .credentials file."""
    RECON_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CREDENTIALS_FILE, 'w') as f:
        f.write("# Recon credentials — DO NOT COMMIT\n")
        for key, value in creds.items():
            f.write(f"{key}={value}\n")


def load_config() -> ReconConfig:
    """Load full recon configuration from env/credentials."""
    competitors = load_competitors()
    creds = load_credentials()

    llm_api_key = (creds.get("llm_api_key") or creds.get("LLM_API_KEY")
                   or creds.get("openai_api_key") or creds.get("OPENAI_API_KEY"))
    transcribe_api_key = (creds.get("transcribe_api_key") or creds.get("TRANSCRIBE_API_KEY")
                          or creds.get("openai_api_key") or creds.get("OPENAI_API_KEY"))

    return ReconConfig(
        competitors=competitors,
        ig_username=creds.get("ig_username") or creds.get("IG_USERNAME"),
        ig_password=creds.get("ig_password") or creds.get("IG_PASSWORD"),
        llm_api_key=llm_api_key,
        llm_base_url=creds.get("llm_base_url") or creds.get("LLM_BASE_URL", "https://api.openai.com/v1"),
        llm_model=creds.get("llm_model") or creds.get("LLM_MODEL", "gpt-4o-mini"),
        llm_provider=creds.get("llm_provider", "custom"),
        transcribe_api_key=transcribe_api_key,
        transcribe_base_url=creds.get("transcribe_base_url") or creds.get("TRANSCRIBE_BASE_URL", "https://api.openai.com/v1"),
        transcribe_model=creds.get("transcribe_model") or creds.get("TRANSCRIBE_MODEL", "whisper-1"),
        transcribe_provider=creds.get("transcribe_provider") or creds.get("TRANSCRIBE_PROVIDER", "openai"),
        whisper_model=creds.get("whisper_model") or creds.get("WHISPER_MODEL", "small.en"),
    )


def get_ig_competitors() -> List[Competitor]:
    """Get only Instagram competitors."""
    return [c for c in load_competitors() if c.platform == "instagram"]


def get_yt_competitors() -> List[Competitor]:
    """Get only YouTube competitors."""
    return [c for c in load_competitors() if c.platform == "youtube"]