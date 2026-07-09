"""Environment and API key management for last30days skill.

Reads config from:
  1. Environment variables (highest priority)
  2. Project root .env file
  3. ~/.config/last30days/.env (legacy fallback)

Each provider can be:
  - {NAME}_API_KEY    — API key (omit if auth not needed)
  - {NAME}_BASE_URL   — Custom endpoint (omit to use default)
  - {NAME}_ENABLED    — Set "false" to disable (default: "true")

Providers with no API key requirement (Bird X, yt-dlp) use
_ENABLED toggles only.
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any


def _find_project_root() -> Optional[Path]:
    """Walk up from cwd to find project root (where .env.example or setup.py lives)."""
    cwd = Path.cwd().resolve()
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".env.example").exists() or (parent / "setup.py").exists() or (parent / "requirements.txt").exists():
            return parent
    return None


_PROJECT_ROOT = _find_project_root()

# Allow override via environment variable for testing
# Set LAST30DAYS_CONFIG_DIR="" for clean/no-config mode
_config_override = os.environ.get('LAST30DAYS_CONFIG_DIR')
if _config_override == "":
    CONFIG_DIR = None
    CONFIG_FILE = None
elif _config_override:
    CONFIG_DIR = Path(_config_override)
    CONFIG_FILE = CONFIG_DIR / ".env"
else:
    CONFIG_DIR = Path.home() / ".config" / "last30days"
    CONFIG_FILE = CONFIG_DIR / ".env"

_PROJECT_ENV_FILE = (_PROJECT_ROOT / ".env") if _PROJECT_ROOT else None


def _load_env_file(path: Optional[Path]) -> Dict[str, str]:
    """Load environment variables from a file."""
    env = {}
    if not path or not path.exists():
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
                    comment_pos = value.find(' #')
                    if comment_pos > 0:
                        value = value[:comment_pos].strip()
                    env[key] = value
    return env


def get_config() -> Dict[str, Any]:
    """Load configuration from .env files and environment.

    Priority: process.env > project .env > ~/.config/last30days/.env
    """
    # Load from files (lowest priority first)
    legacy_env = _load_env_file(CONFIG_FILE) if CONFIG_FILE else {}
    project_env = _load_env_file(_PROJECT_ENV_FILE) if _PROJECT_ENV_FILE else {}

    # Merge: project overrides legacy, env overrides all
    merged = {**legacy_env, **project_env}

    # Provider configuration keys with defaults
    provider_keys = [
        # Reddit discovery (OpenAI Responses API)
        ('OPENAI_API_KEY', None),
        ('OPENAI_REDDIT_ENABLED', 'true'),
        ('OPENAI_REDDIT_BASE_URL', None),
        ('OPENAI_REDDIT_MODEL', 'gpt-4.1'),
        ('OPENAI_MODEL_POLICY', 'auto'),
        ('OPENAI_MODEL_PIN', None),

        # X/Twitter search (xAI API)
        ('XAI_API_KEY', None),
        ('XAI_X_ENABLED', 'true'),
        ('XAI_X_BASE_URL', None),
        ('XAI_MODEL_POLICY', 'latest'),
        ('XAI_MODEL_PIN', None),

        # OpenRouter / Perplexity Sonar Pro
        ('OPENROUTER_API_KEY', None),
        ('OPENROUTER_SEARCH_ENABLED', 'true'),
        ('OPENROUTER_BASE_URL', None),
        ('OPENROUTER_MODEL', 'perplexity/sonar-pro'),

        # Parallel AI Search
        ('PARALLEL_API_KEY', None),
        ('PARALLEL_SEARCH_ENABLED', 'true'),
        ('PARALLEL_BASE_URL', None),

        # Brave Search
        ('BRAVE_API_KEY', None),
        ('BRAVE_SEARCH_ENABLED', 'true'),
        ('BRAVE_BASE_URL', None),

        # YouTube (yt-dlp, no key)
        ('YOUTUBE_ENABLED', 'true'),
    ]

    config = {}
    for key, default in provider_keys:
        # Check env first, then merged file env, then default
        config[key] = os.environ.get(key) or merged.get(key, default)

    return config


def config_exists() -> bool:
    """Check if any configuration file exists."""
    if _PROJECT_ENV_FILE and _PROJECT_ENV_FILE.exists():
        return True
    return CONFIG_FILE.exists() if CONFIG_FILE else False


def is_provider_enabled(config: dict, key: str) -> bool:
    """Check if a provider is enabled via its _ENABLED flag."""
    enabled = config.get(key, 'true')
    return str(enabled).lower() in ('true', '1', 'yes')


def get_available_sources(config: Dict[str, Any]) -> str:
    """Determine which sources are available based on API keys.

    Returns: 'all', 'both', 'reddit', 'reddit-web', 'x', 'x-web', 'web', or 'none'
    """
    has_openai = bool(config.get('OPENAI_API_KEY')) and is_provider_enabled(config, 'OPENAI_REDDIT_ENABLED')
    has_xai = bool(config.get('XAI_API_KEY')) and is_provider_enabled(config, 'XAI_X_ENABLED')
    has_web = has_web_search_keys(config)

    if has_openai and has_xai:
        return 'all' if has_web else 'both'
    elif has_openai:
        return 'reddit-web' if has_web else 'reddit'
    elif has_xai:
        return 'x-web' if has_web else 'x'
    elif has_web:
        return 'web'
    else:
        return 'web'


def has_web_search_keys(config: Dict[str, Any]) -> bool:
    """Check if any web search API keys are configured and enabled."""
    openrouter = bool(config.get('OPENROUTER_API_KEY')) and is_provider_enabled(config, 'OPENROUTER_SEARCH_ENABLED')
    parallel = bool(config.get('PARALLEL_API_KEY')) and is_provider_enabled(config, 'PARALLEL_SEARCH_ENABLED')
    brave = bool(config.get('BRAVE_API_KEY')) and is_provider_enabled(config, 'BRAVE_SEARCH_ENABLED')
    return openrouter or parallel or brave


def get_web_search_source(config: Dict[str, Any]) -> Optional[str]:
    """Determine the best available web search backend.

    Priority: Parallel AI > Brave > OpenRouter/Sonar Pro

    Each is checked for API key AND enabled flag.
    """
    if config.get('PARALLEL_API_KEY') and is_provider_enabled(config, 'PARALLEL_SEARCH_ENABLED'):
        return 'parallel'
    if config.get('BRAVE_API_KEY') and is_provider_enabled(config, 'BRAVE_SEARCH_ENABLED'):
        return 'brave'
    if config.get('OPENROUTER_API_KEY') and is_provider_enabled(config, 'OPENROUTER_SEARCH_ENABLED'):
        return 'openrouter'
    return None


def get_missing_keys(config: Dict[str, Any]) -> str:
    """Determine which sources are missing (accounting for Bird).

    Returns: 'all', 'both', 'reddit', 'x', 'web', or 'none'
    """
    has_openai = bool(config.get('OPENAI_API_KEY')) and is_provider_enabled(config, 'OPENAI_REDDIT_ENABLED')
    has_xai = bool(config.get('XAI_API_KEY')) and is_provider_enabled(config, 'XAI_X_ENABLED')
    has_web = has_web_search_keys(config)

    from . import bird_x
    has_bird = bird_x.is_bird_installed() and bird_x.is_bird_authenticated()

    has_x = has_xai or has_bird

    if has_openai and has_x and has_web:
        return 'none'
    elif has_openai and has_x:
        return 'web'
    elif has_openai:
        return 'x'
    elif has_x:
        return 'reddit'
    else:
        return 'all'


def validate_sources(requested: str, available: str, include_web: bool = False) -> tuple[str, Optional[str]]:
    """Validate requested sources against available keys.

    Args:
        requested: 'auto', 'reddit', 'x', 'both', or 'web'
        available: Result from get_available_sources()
        include_web: If True, add WebSearch to available sources

    Returns:
        Tuple of (effective_sources, error_message)
    """
    if available == 'none':
        if requested == 'auto':
            return 'web', "No API keys configured. The assistant can still search the web if it has a search tool."
        elif requested == 'web':
            return 'web', None
        else:
            return 'web', f"No API keys configured. Add keys to project .env for Reddit/X."

    if available == 'web':
        if requested in ('auto', 'web'):
            return 'web', None
        else:
            return 'web', f"Only web search keys configured. Add OPENAI_API_KEY for Reddit, XAI_API_KEY for X."

    if requested == 'auto':
        if include_web:
            if available == 'both':
                return 'all', None
            elif available == 'reddit':
                return 'reddit-web', None
            elif available == 'x':
                return 'x-web', None
        return available, None

    if requested == 'web':
        return 'web', None

    if requested == 'both':
        if available not in ('both',):
            missing = 'xAI' if available == 'reddit' else 'OpenAI'
            return 'none', f"Requested both sources but {missing} key is missing. Use --sources=auto to use available keys."
        if include_web:
            return 'all', None
        return 'both', None

    if requested == 'reddit':
        if available == 'x':
            return 'none', "Requested Reddit but only xAI key is available."
        if include_web:
            return 'reddit-web', None
        return 'reddit', None

    if requested == 'x':
        if available == 'reddit':
            return 'none', "Requested X but only OpenAI key is available."
        if include_web:
            return 'x-web', None
        return 'x', None

    return requested, None


def get_x_source(config: Dict[str, Any]) -> Optional[str]:
    """Determine the best available X/Twitter source.

    Priority: Bird (free) -> xAI (paid API)

    Returns:
        'bird' if Bird is installed and authenticated,
        'xai' if XAI_API_KEY is configured,
        None if no X source available.
    """
    from . import bird_x

    if bird_x.is_bird_installed():
        username = bird_x.is_bird_authenticated()
        if username:
            return 'bird'

    if config.get('XAI_API_KEY') and is_provider_enabled(config, 'XAI_X_ENABLED'):
        return 'xai'

    return None


def is_ytdlp_available() -> bool:
    """Check if yt-dlp is installed for YouTube search."""
    from . import youtube_yt
    if not youtube_yt.is_ytdlp_installed():
        return False
    return True


def get_x_source_status(config: Dict[str, Any]) -> Dict[str, Any]:
    """Get detailed X source status for UI decisions.

    Returns:
        Dict with keys: source, bird_installed, bird_authenticated,
        bird_username, xai_available, can_install_bird
    """
    from . import bird_x

    bird_status = bird_x.get_bird_status()
    xai_available = bool(config.get('XAI_API_KEY')) and is_provider_enabled(config, 'XAI_X_ENABLED')

    if bird_status["authenticated"]:
        source = 'bird'
    elif xai_available:
        source = 'xai'
    else:
        source = None

    return {
        "source": source,
        "bird_installed": bird_status["installed"],
        "bird_authenticated": bird_status["authenticated"],
        "bird_username": bird_status["username"],
        "xai_available": xai_available,
        "can_install_bird": bird_status["can_install"],
    }