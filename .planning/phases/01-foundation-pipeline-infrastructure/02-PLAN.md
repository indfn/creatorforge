---
title: "QuotaBudget Shared Service"
wave: 1
requirements: [PIPE-04]
depends_on: []
files_modified:
  - agent_core/core/quota.py
  - schemas/quota-budget.schema.json
autonomous: true
---

## Objective

Build a `QuotaBudget` shared service that tracks daily API consumption per named budget (e.g., `youtube_data`, `youtube_analytics`, `pexels`, `gemini`), persists daily state with file locking, and rejects requests when budget is exhausted.

## Background

Currently there is no centralized rate-limit management. The codebase has ad-hoc `time.sleep(1)` (Instagram scraper), linear backoff on 429 (downloader), and exponential backoff in the LLM client — but no pre-flight quota check. The `QuotaBudget` service provides a shared singleton that all quota-aware pipeline stages call before making API requests.

## Tasks

### Task 2.1: Define QuotaBudget JSON Schema

<read_first>
- schemas/production-order.schema.json (existing schema pattern)
</read_first>

<action>

Create `schemas/quota-budget.schema.json`:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Quota Budget",
  "description": "Daily quota budget tracking per API service — persists daily consumption",
  "type": "object",
  "required": ["budgets", "date", "version"],
  "properties": {
    "budgets": {
      "type": "object",
      "patternProperties": {
        "^[a-z_]+$": {
          "type": "object",
          "required": ["daily_limit", "consumed", "remaining"],
          "properties": {
            "daily_limit": { "type": "integer", "minimum": 1, "description": "Maximum units per day" },
            "consumed": { "type": "integer", "minimum": 0, "description": "Units consumed today" },
            "remaining": { "type": "integer", "minimum": 0 },
            "last_reset": { "type": "string", "format": "date-time" },
            "description": { "type": "string" }
          }
        }
      }
    },
    "date": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$", "description": "ISO date of current budget day" },
    "version": { "type": "integer", "minimum": 1 }
  }
}
```

</action>

<acceptance_criteria>
- `schemas/quota-budget.schema.json` exists and is valid JSON Schema draft-07
- Schema requires `budgets` (object), `date` (ISO date string), `version` (integer)
- Each budget entry requires `daily_limit`, `consumed`, `remaining`
- `python -m json.tool schemas/quota-budget.schema.json` succeeds
</acceptance_criteria>

---

### Task 2.2: Implement QuotaBudget Service

<read_first>
- schemas/quota-budget.schema.json (new from Task 2.1)
- agent_core/recon/utils/state_manager.py (existing state persistence pattern)
</read_first>

<action>

Create `agent_core/core/quota.py` with:

```python
"""
QuotaBudget — shared service for daily API quota tracking.
All quota-aware pipeline stages call consume() before making API requests.
"""

import json
import os
from pathlib import Path
from datetime import date, datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional

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
    Shared daily quota tracker. Thread-safe via file-level lock (portalocker
    added in Plan 3).
    
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
        self._state = self._load_or_init()

    def _load_or_init(self) -> dict:
        """Load persisted state or initialize fresh for today."""
        today = date.today().isoformat()
        if self.budgets_file.exists():
            try:
                with open(self.budgets_file, "r") as f:
                    data = json.load(f)
                validate_or_raise(data, "quota-budget.schema.json")
                if data.get("date") == today:
                    return data
                # New day — reset consumed counters
                return self._reset_for_new_day(data)
            except (json.JSONDecodeError, ValueError):
                pass  # Fall through to fresh init

        return self._fresh_state(today)

    def _fresh_state(self, today: str) -> dict:
        """Initialize fresh state with default budgets."""
        budgets = {}
        for name, cfg in DEFAULT_BUDGETS.items():
            budgets[name] = {
                "daily_limit": cfg["daily_limit"],
                "consumed": 0,
                "remaining": cfg["daily_limit"],
                "last_reset": datetime.now(timezone.utc).isoformat(),
                "description": cfg.get("description", ""),
            }
        return {"budgets": budgets, "date": today, "version": 1}

    def _reset_for_new_day(self, old_state: dict) -> dict:
        """Reset consumed counters for a new day, preserving limits."""
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
        """Write state to disk atomically."""
        tmp = self.budgets_file.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(self._state, f, indent=2)
        tmp.rename(self.budgets_file)

    def can_consume(self, budget_name: str, amount: int = 1) -> bool:
        """Check if budget has enough remaining units."""
        entry = self._state["budgets"].get(budget_name)
        if entry is None:
            return False
        return entry["remaining"] >= amount

    def consume(self, budget_name: str, amount: int = 1) -> bool:
        """
        Consume quota units. Returns True if successful, False if budget exhausted.
        """
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
        """Get remaining units for a budget."""
        entry = self._state["budgets"].get(budget_name)
        if entry is None:
            return 0
        return entry["remaining"]

    def get_summary(self) -> dict:
        """Get full budget summary (for reporting/monitoring)."""
        return dict(self._state)

    def reset_budget(self, budget_name: str):
        """Reset a single budget's consumed counter."""
        entry = self._state["budgets"].get(budget_name)
        if entry:
            entry["consumed"] = 0
            entry["remaining"] = entry["daily_limit"]
            entry["last_reset"] = datetime.now(timezone.utc).isoformat()
            self._persist()

    def add_budget(self, name: str, daily_limit: int, description: str = ""):
        """Add or update a budget definition."""
        self._state["budgets"][name] = {
            "daily_limit": daily_limit,
            "consumed": 0,
            "remaining": daily_limit,
            "last_reset": datetime.now(timezone.utc).isoformat(),
            "description": description,
        }
        self._persist()
```

</action>

<acceptance_criteria>
- `agent_core/core/quota.py` exists with `QuotaBudget` class
- `from agent_core.core.quota import QuotaBudget` works
- `QuotaBudget().consume("youtube_data", 1600)` returns `True` and decrements remaining
- `QuotaBudget().consume("nonexistent", 1)` returns `False`
- `QuotaBudget().can_consume("youtube_data", 1)` returns `True` when quota available
- Budget auto-resets on new day (date change)
- State persists to `data/quota/budget.json` and reloads correctly
- `get_summary()` returns all budget states
- `add_budget()` adds a new tracked budget
- State file validates against `quota-budget.schema.json`
</acceptance_criteria>

---

### Task 2.3: Write defaults.json with documented limits

<read_first>
- schemas/quota-budget.schema.json
- agent_core/core/quota.py (for DEFAULT_BUDGETS)
</read_first>

<action>

Create `data/quota/defaults.json` with documented limits for reference (not used at runtime — `QuotaBudget` has defaults baked in):
```json
{
  "$schema": "../../schemas/quota-budget.schema.json#/properties/budgets",
  "youtube_data": { "daily_limit": 10000, "description": "YouTube Data API v3 — 10,000 units/day default quota" },
  "youtube_upload": { "daily_limit": 6, "description": "~6 uploads/day (1,600 units each)" },
  "youtube_analytics": { "daily_limit": 500, "description": "YouTube Analytics API" },
  "gemini_tts": { "daily_limit": 1500, "description": "Gemini TTS API calls" },
  "pexels": { "daily_limit": 200, "description": "Pexels photo/video API" },
  "pixabay": { "daily_limit": 5000, "description": "Pixabay image API" },
  "freesound": { "daily_limit": 500, "description": "Freesound SFX API" }
}
```

</action>

<acceptance_criteria>
- `data/quota/defaults.json` exists with all 7 documented budget entries
- File is valid JSON: `python -m json.tool data/quota/defaults.json` succeeds
</acceptance_criteria>

## Verification

1. `python -c "from agent_core.core.quota import QuotaBudget; q=QuotaBudget(); print(q.remaining('youtube_data'))"` prints `10000`
2. Consume 1600 units, verify remaining is 8400
3. Consume all remaining units, verify `can_consume()` returns `False`
4. Delete `data/quota/budget.json`, re-create `QuotaBudget()` — fresh state for today
5. Change system date (mock), instantiate `QuotaBudget()` — verify auto-reset
6. `python -m json.tool schemas/quota-budget.schema.json` exits 0

## Must Haves

- [ ] `consume()` decrements remaining and persists to disk
- [ ] `can_consume()` returns false when budget is exhausted
- [ ] Daily auto-reset on date change (detected at init)
- [ ] All 7 default budgets pre-configured

## Must Nots

- [ ] Do NOT integrate quota into pipeline stages yet (that's later phases)
- [ ] Do NOT add file locking yet (that's Plan 3)
- [ ] Do NOT add env-var override for limits (can be done later if needed)
