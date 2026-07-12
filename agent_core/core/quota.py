"""
QuotaBudget — shared service for daily API quota tracking.
All quota-aware pipeline stages call consume() before making API requests.
"""

import json
import os
import threading
from pathlib import Path
from datetime import date, datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional

import portalocker

from agent_core.core.validation import validate_or_raise


QUOTA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "quota"
QUOTA_FILE = QUOTA_DIR / "budget.json"
DEFAULT_QUOTA_FILE = QUOTA_DIR / "defaults.json"


DEFAULT_BUDGETS: dict[str, dict] = {
    "youtube_data": {"daily_limit": 10000, "description": "YouTube Data API v3 (search, channels, playlists)"},
    "youtube_upload": {"daily_limit": 6, "description": "YouTube uploads (1,600 units each, 10K daily = ~6/day)"},
    "youtube_analytics": {"daily_limit": 500, "description": "YouTube Analytics API (reports)"},
    "gemini_tts": {"daily_limit": 1500, "description": "Gemini TTS requests"},
    "pexels": {"daily_limit": 200, "description": "Pexels photo/video API"},
    "pixabay": {"daily_limit": 5000, "description": "Pixabay image API"},
    "freesound": {"daily_limit": 500, "description": "Freesound SFX API"},
}


@dataclass
class BudgetEntry:
    daily_limit: int
    consumed: int = 0
    remaining: int = 0
    last_reset: str = ""
    description: str = ""

    def __post_init__(self):
        self.remaining = max(0, self.daily_limit - self.consumed)
        if not self.last_reset:
            self.last_reset = datetime.now(timezone.utc).isoformat()


class QuotaBudget:
    """
    Shared daily quota tracker.

    Usage:
        quota = QuotaBudget()
        if quota.can_consume("youtube_data", 1600):
            quota.consume("youtube_data", 1600)
            # make API call
        else:
            logger.warning("QUOTA", "YouTube Data API quota exhausted")
    """

    def __init__(self, budgets_file: Optional[Path] = None):
        self.budgets_file = budgets_file or QUOTA_FILE
        self.budgets_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._state = self._load_or_init()

    def _load_or_init(self) -> dict:
        """Load persisted state or initialize fresh for today."""
        today = date.today().isoformat()
        if self.budgets_file.exists():
            with self._lock:
                with open(self.budgets_file, "r") as f:
                    portalocker.lock(f, portalocker.LOCK_SH)
                    try:
                        data = json.load(f)
                    finally:
                        portalocker.unlock(f)
                try:
                    validate_or_raise(data, "quota-budget.schema.json")
                    if data.get("date") == today:
                        return data
                    return self._reset_for_new_day(data)
                except (json.JSONDecodeError, ValueError):
                    pass

        return self._fresh_state(today)

    def _fresh_state(self, today: str) -> dict:
        """Initialize fresh state from defaults.json, falling back to hardcoded defaults."""
        try:
            with open(DEFAULT_QUOTA_FILE, "r") as f:
                default_budgets = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            default_budgets = DEFAULT_BUDGETS

        budgets = {}
        for name, cfg in default_budgets.items():
            if isinstance(cfg, dict) and "daily_limit" in cfg:
                budgets[name] = {
                    "daily_limit": cfg["daily_limit"],
                    "consumed": 0,
                    "remaining": cfg["daily_limit"],
                    "last_reset": datetime.now(timezone.utc).isoformat(),
                    "description": cfg.get("description", ""),
                }
        return {"budgets": budgets, "date": today, "version": 1}

    def _reset_for_new_day(self, old_state: dict) -> dict:
        today = date.today().isoformat()
        budgets = {}
        for name, entry in old_state.get("budgets", {}).items():
            limit = entry.get("daily_limit", 1000)
            budgets[name] = {
                "daily_limit": limit,
                "consumed": 0,
                "remaining": limit,
                "last_reset": datetime.now(timezone.utc).isoformat(),
                "description": entry.get("description", ""),
            }
        return {"budgets": budgets, "date": today, "version": 1}

    def _persist(self):
        """Write state to disk atomically with file locking."""
        tmp = self.budgets_file.with_suffix(".tmp")
        with self._lock:
            with open(tmp, "w") as f:
                portalocker.lock(f, portalocker.LOCK_EX)
                try:
                    json.dump(self._state, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    portalocker.unlock(f)
            tmp.rename(self.budgets_file)

    def can_consume(self, budget_name: str, amount: int = 1) -> bool:
        entry = self._state["budgets"].get(budget_name)
        if entry is None:
            return False
        return entry["remaining"] >= amount

    def consume(self, budget_name: str, amount: int = 1) -> bool:
        entry = self._state["budgets"].get(budget_name)
        if entry is None:
            return False
        if entry["remaining"] < amount:
            return False
        entry["consumed"] += amount
        entry["remaining"] = max(0, entry["daily_limit"] - entry["consumed"])
        self._persist()
        return True

    def remaining(self, budget_name: str) -> int:
        entry = self._state["budgets"].get(budget_name)
        if entry is None:
            return 0
        return entry["remaining"]

    def get_summary(self) -> dict:
        return dict(self._state)

    def reset_budget(self, budget_name: str):
        entry = self._state["budgets"].get(budget_name)
        if entry:
            entry["consumed"] = 0
            entry["remaining"] = entry["daily_limit"]
            entry["last_reset"] = datetime.now(timezone.utc).isoformat()
            self._persist()

    def add_budget(self, name: str, daily_limit: int, description: str = ""):
        self._state["budgets"][name] = {
            "daily_limit": daily_limit,
            "consumed": 0,
            "remaining": daily_limit,
            "last_reset": datetime.now(timezone.utc).isoformat(),
            "description": description,
        }
        self._persist()
