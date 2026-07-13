"""
scripts package — make hyphen-named scripts importable as Python modules.

Script filenames use hyphens (e.g. fetch-ig-insights.py) which are not valid
Python identifiers. This module registers them in sys.modules (for import
machinery) and makes them available as attributes (for attribute access).

Usage::

    from scripts.fetch_ig_insights import get_media_insights
"""

import importlib.util
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent

# Maps underscored importable name → actual hyphenated filename
_HYPHEN_MODULES: dict[str, str] = {
    "fetch_ig_insights": "fetch-ig-insights.py",
    "fetch_yt_analytics": "fetch-yt-analytics.py",
    "generate_pdf": "generate-pdf.py",
    "setup_ig_token": "setup-ig-token.py",
    "setup_yt_oauth": "setup-yt-oauth.py",
    "setup_channel_branding": "setup-channel-branding.py",
}

_PREFIX = __name__  # "scripts"


def _ensure_loaded(name: str):
    """Load *name* module into sys.modules if not already there."""
    import_name = f"{_PREFIX}.{name}"
    if import_name in sys.modules:
        return sys.modules[import_name]

    filename = _HYPHEN_MODULES.get(name)
    if filename is None:
        return None

    filepath = _SCRIPT_DIR / filename
    if not filepath.exists():
        return None

    spec = importlib.util.spec_from_file_location(import_name, str(filepath))
    if spec is None or spec.loader is None:
        return None

    mod = importlib.util.module_from_spec(spec)
    sys.modules[import_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── Pre-register all known hyphen modules into sys.modules ────────────
# This ensures that ``from scripts.fetch_ig_insights import ...`` works
# via the standard import machinery (importlib checks sys.modules first).
for _name in _HYPHEN_MODULES:
    _ensure_loaded(_name)


def __getattr__(name: str):
    """Lazy-load hyphen module when accessed as ``scripts.fetch_ig_insights``."""
    mod = _ensure_loaded(name)
    if mod is not None:
        return mod
    msg = f"module {_PREFIX!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:  # type: ignore[no-untyped-def]
    """Include hyphen-module names in directory listing."""
    return [*object.__dir__(object()), *_HYPHEN_MODULES.keys()]
