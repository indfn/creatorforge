"""
Recon — Configuration module.
Reads competitor list from agent-brain.json, manages credentials and API keys.
Credentials loaded from .env (project root). Legacy .credentials file as fallback.
"""

import os
import json
from pathlib import Path
import stat
from typing import Optional, Dict, List
from dataclasses import dataclass
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken


PIPELINE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = PIPELINE_DIR / "data"
RECON_DATA_DIR = DATA_DIR / "recon"
CREDENTIALS_FILE = RECON_DATA_DIR / ".credentials"
BRAIN_FILE = DATA_DIR / "agent-brain.json"
ENV_FILE = PIPELINE_DIR / ".env"
CREDENTIALS_KEY_DIR = Path.home() / ".creatorforge"
CREDENTIALS_KEY_FILE = CREDENTIALS_KEY_DIR / "credentials.key"


def _get_encryption_key() -> bytes:
    """Get the Fernet encryption key for credential storage.

    Priority:
    1. CREDENTIALS_ENCRYPTION_KEY environment variable
    2. ~/.creatorforge/credentials.key file (created on first use)
    3. Auto-generate and persist to ~/.creatorforge/credentials.key
    """
    env_key = os.environ.get("CREDENTIALS_ENCRYPTION_KEY")
    if env_key:
        return env_key.encode("utf-8")

    if CREDENTIALS_KEY_FILE.exists():
        return CREDENTIALS_KEY_FILE.read_bytes()

    # Generate a new key on first use
    key = Fernet.generate_key()
    CREDENTIALS_KEY_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_KEY_FILE.write_bytes(key)
    CREDENTIALS_KEY_FILE.chmod(0o600)
    return key


def _encrypt_credentials(creds: Dict[str, str]) -> bytes:
    """Encrypt credentials dict as JSON with Fernet."""
    key = _get_encryption_key()
    fernet = Fernet(key)
    plaintext = json.dumps(creds, ensure_ascii=False, indent=2).encode("utf-8")
    return fernet.encrypt(plaintext)


def _decrypt_credentials(data: bytes) -> Optional[Dict[str, str]]:
    """Decrypt Fernet-encrypted credentials. Returns None if decryption fails."""
    try:
        key = _get_encryption_key()
        fernet = Fernet(key)
        plaintext = fernet.decrypt(data)
        return json.loads(plaintext.decode("utf-8"))
    except (InvalidToken, Exception):
        return None


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

    # Load .credentials — try encrypted (Fernet) first, fall back to legacy plaintext
    if CREDENTIALS_FILE.exists():
        raw = CREDENTIALS_FILE.read_bytes()
        decrypted = _decrypt_credentials(raw)
        if decrypted is not None:
            creds.update(decrypted)
        else:
            # Legacy plaintext fallback
            for line in raw.decode("utf-8").splitlines():
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    if k.strip() not in creds:
                        creds[k.strip()] = v.strip()

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
    """Save credentials to .credentials file (encrypted with Fernet, 0600 perms)."""
    RECON_DATA_DIR.mkdir(parents=True, exist_ok=True)
    encrypted = _encrypt_credentials(creds)
    CREDENTIALS_FILE.write_bytes(encrypted)
    CREDENTIALS_FILE.chmod(0o600)


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