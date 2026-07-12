---
title: "Safety & Resilience — File Locking, LRU Cache, Scene Checkpoints"
wave: 2
requirements: [PIPE-05, PIPE-06, PIPE-07]
depends_on:
  - 01-PLAN.md
  - 02-PLAN.md
files_modified:
  - agent_core/core/jobs.py
  - agent_core/core/checkpoint.py
  - agent_core/recon/tracker.py
  - agent_core/recon/utils/state_manager.py
  - agent_core/core/quota.py
  - requirements.txt
autonomous: true
---

## Objective

Harden all stateful components against concurrent access (file locking via `portalocker`), cap in-memory growth (LRU eviction for `active_jobs`), and wire scene-level checkpoint granularity into the `CheckpointManager`.

## Background

- **PIPE-05**: State files (tracker, job states, quota budget, checkpoints) have no file locking — concurrent processes can corrupt each other's writes. `portalocker` provides cross-platform file locking.
- **PIPE-06**: The in-memory `active_jobs` dict has no size cap — unbounded growth under heavy load.
- **PIPE-07**: Scene-level checkpointing (each scene's audio, subtitles, rendered clip checkpoint independently) is designed in the `CheckpointManager` but not yet wired into a real pipeline.

## Tasks

### Task 3.1: Add `portalocker` dependency

<read_first>
- requirements.txt
</read_first>

<action>
Add `portalocker>=2.8.2` to `requirements.txt`.
</action>

<acceptance_criteria>
- `requirements.txt` contains `portalocker>=2.8.2`
- `python -c "import portalocker; print(portalocker.__version__)"` exits 0 after install
</acceptance_criteria>

---

### Task 3.2: Add file locking to CheckpointManager

<read_first>
- agent_core/core/checkpoint.py (needs locking on all file writes)
</read_first>

<action>

Modify `agent_core/core/checkpoint.py`:

1. Add import: `import portalocker`
2. Add a `_LOCK` class-level `threading.Lock` for in-process safety
3. Wrap `save_checkpoint()` write with portalocker:

```python
import portalocker
import threading

class CheckpointManager:
    _file_lock = threading.Lock()

    def save_checkpoint(self, ...):
        # ... existing validation ...
        path = self._checkpoint_path(pipeline_id, stage, scene_id)
        tmp_path = path.with_suffix(".tmp")

        with self._file_lock:
            with open(tmp_path, "w") as f:
                portalocker.lock(f, portalocker.LOCK_EX)
                try:
                    json.dump(asdict(checkpoint), f, indent=2, default=str)
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    portalocker.unlock(f)
            tmp_path.rename(path)

        return checkpoint
```

4. Add `os` import at top of file.

5. Also wrap `load_checkpoint()` reads:

```python
def load_checkpoint(self, ...):
    path = self._checkpoint_path(pipeline_id, stage, scene_id)
    if not path.exists():
        return None
    with self._file_lock:
        with open(path, "r") as f:
            portalocker.lock(f, portalocker.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                portalocker.unlock(f)
    return Checkpoint(**data)
```

</action>

<acceptance_criteria>
- `agent_core/core/checkpoint.py` imports `portalocker`
- `save_checkpoint()` acquires an exclusive file lock during write
- `load_checkpoint()` acquires a shared file lock during read
- In-process thread safety via `threading.Lock`
- Concurrent writes to the same checkpoint file are serialized
- After a crash during write, `.tmp` files may remain but `.json` files are never partial
</acceptance_criteria>

---

### Task 3.3: Add file locking to tracker.py

<read_first>
- agent_core/recon/tracker.py
</read_first>

<action>

Modify `agent_core/recon/tracker.py`:

1. Add imports: `import portalocker`, `import os`, `import threading`
2. Add module-level lock: `_tracker_lock = threading.Lock()`
3. Wrap `save_state()` with portalocker exclusive lock:

```python
def save_state(state: Dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _tracker_lock:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            portalocker.lock(f, portalocker.LOCK_EX)
            try:
                json.dump(state, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            finally:
                portalocker.unlock(f)
```

4. Wrap `load_state()` with portalocker shared lock:

```python
def load_state() -> Dict:
    if not STATE_FILE.exists():
        return {}
    with _tracker_lock:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            portalocker.lock(f, portalocker.LOCK_SH)
            try:
                return json.load(f)
            finally:
                portalocker.unlock(f)
```

5. Update the `cleanup_old_entries()` function to use locked `load_state()`/`save_state()`:

```python
def cleanup_old_entries(state: Optional[Dict] = None, max_age_days: int = 30) -> Dict:
    if state is None:
        state = load_state()
    # ... existing logic ...
    save_state(cleaned)
    return cleaned
```

</action>

<acceptance_criteria>
- `agent_core/recon/tracker.py` imports `portalocker`
- `save_state()` acquires exclusive file lock
- `load_state()` acquires shared file lock
- `save_state()` calls `os.fsync()` before releasing lock
- `cleanup_old_entries()` uses locked `load_state()`/`save_state()`
</acceptance_criteria>

---

### Task 3.4: Add file locking to state_manager.py

<read_first>
- agent_core/recon/utils/state_manager.py
</read_first>

<action>

Modify `agent_core/recon/utils/state_manager.py`:

1. Add imports: `import portalocker`, `import os`, `import threading`
2. Add instance-level lock: `self._lock = threading.Lock()` in `__init__`
3. Wrap `save_job_state()`:

```python
def save_job_state(self, job_id: str, state: Dict[str, Any]):
    path = self.state_dir / f"{job_id}.json"
    state["updated_at"] = datetime.utcnow().isoformat()
    with self._lock:
        tmp = path.with_suffix(".tmp")
        with open(tmp, 'w', encoding='utf-8') as f:
            portalocker.lock(f, portalocker.LOCK_EX)
            try:
                json.dump(state, f, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())
            finally:
                portalocker.unlock(f)
        tmp.rename(path)
```

4. Wrap `load_job_state()`:

```python
def load_job_state(self, job_id: str) -> Optional[Dict[str, Any]]:
    path = self.state_dir / f"{job_id}.json"
    if not path.exists():
        return None
    with self._lock:
        with open(path, 'r', encoding='utf-8') as f:
            portalocker.lock(f, portalocker.LOCK_SH)
            try:
                return json.load(f)
            finally:
                portalocker.unlock(f)
```

</action>

<acceptance_criteria>
- `agent_core/recon/utils/state_manager.py` imports `portalocker`
- `save_job_state()` uses atomic write (tmp file + rename) with exclusive lock
- `load_job_state()` uses shared lock
- Instance-level `threading.Lock` prevents in-process races
</acceptance_criteria>

---

### Task 3.5: Add file locking to QuotaBudget persistence

<read_first>
- agent_core/core/quota.py
</read_first>

<action>

Modify `agent_core/core/quota.py`:

1. Add imports: `import portalocker`, `import os`, `import threading`
2. Add instance lock: `self._lock = threading.Lock()` in `__init__`
3. Wrap `_persist()`:

```python
def _persist(self):
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
```

4. Wrap `_load_or_init()` read:

```python
def _load_or_init(self) -> dict:
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
```

</action>

<acceptance_criteria>
- `agent_core/core/quota.py` imports `portalocker`
- `_persist()` uses exclusive lock with `os.fsync()`
- `_load_or_init()` uses shared lock
- Instance lock prevents concurrent in-process modifications
</acceptance_criteria>

---

### Task 3.6: Implement LRU ActiveJobs cache

<read_first>
- agent_core/core/pipeline.py (how Stage and PipelineResult reference jobs)
- Pipeline run pattern in agent_core/recon/skeleton_ripper/pipeline.py
</read_first>

<action>

Create `agent_core/core/jobs.py`:

```python
"""
Active Jobs — LRU-evicted in-memory cache for active pipeline jobs.
Prevents unbounded memory growth under heavy load.
"""

import threading
from collections import OrderedDict
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class JobInfo:
    """Runtime metadata for an active pipeline job."""
    pipeline_id: str
    status: str  # "running" | "paused" | "completed" | "failed"
    stage: str = ""
    progress: float = 0.0  # 0.0 to 1.0
    created_at: str = ""
    updated_at: str = ""
    metadata: dict = field(default_factory=dict)


class ActiveJobs:
    """
    LRU-evicted cache of active pipeline jobs.
    
    When capacity is exceeded, the least recently accessed (or added) job
    is evicted. Thread-safe.
    
    Usage:
        jobs = ActiveJobs(maxsize=100)
        jobs.add("pipe_001", JobInfo(pipeline_id="pipe_001", status="running"))
        info = jobs.get("pipe_001")
    """

    def __init__(self, maxsize: int = 100):
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self._maxsize = maxsize
        self._cache: OrderedDict[str, JobInfo] = OrderedDict()
        self._lock = threading.Lock()

    @property
    def maxsize(self) -> int:
        return self._maxsize

    def add(self, job_id: str, info: JobInfo):
        """Add or update a job. Evicts LRU entry if at capacity."""
        now = datetime.now(timezone.utc).isoformat()
        if not info.created_at:
            info.created_at = now
        info.updated_at = now

        with self._lock:
            if job_id in self._cache:
                self._cache.move_to_end(job_id)
                self._cache[job_id] = info
                return
            if len(self._cache) >= self._maxsize:
                evicted_id, _ = self._cache.popitem(last=False)
            self._cache[job_id] = info

    def get(self, job_id: str) -> Optional[JobInfo]:
        """Get job info. Returns None if not found. Marks as recently used."""
        with self._lock:
            if job_id not in self._cache:
                return None
            self._cache.move_to_end(job_id)
            return self._cache[job_id]

    def remove(self, job_id: str) -> bool:
        """Remove a job. Returns True if it existed."""
        with self._lock:
            if job_id in self._cache:
                del self._cache[job_id]
                return True
            return False

    def update_status(self, job_id: str, status: str, stage: str = "", progress: float = 0.0):
        """Update job status in-place."""
        with self._lock:
            info = self._cache.get(job_id)
            if info:
                info.status = status
                info.stage = stage
                info.progress = progress
                info.updated_at = datetime.now(timezone.utc).isoformat()
                self._cache.move_to_end(job_id)

    def list_active(self) -> list[JobInfo]:
        """Return all active (running/paused) jobs in insertion order."""
        with self._lock:
            return [
                info for info in self._cache.values()
                if info.status in ("running", "paused")
            ]

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    def __contains__(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._cache
```

</action>

<acceptance_criteria>
- `agent_core/core/jobs.py` exists with `ActiveJobs` and `JobInfo`
- `from agent_core.core.jobs import ActiveJobs, JobInfo` works
- `add()` stores a job, `get()` retrieves it
- Adding more than `maxsize` jobs evicts the least recently used entry
- `remove()` removes a job and returns `True`
- Thread-safe via `threading.Lock`
- `update_status()` modifies job state in-place
- `list_active()` returns only running/paused jobs
- `maxsize=0` raises `ValueError`
</acceptance_criteria>

---

### Task 3.7: Wire scene-level checkpoint into checkpoint documentation

<read_first>
- agent_core/core/checkpoint.py (scene-level method signatures already exist)
</read_first>

<action>

Modify `agent_core/core/checkpoint.py` to add a convenience method for scene-level batch operations:

```python
def save_scene_checkpoint(
    self,
    pipeline_id: str,
    stage: str,
    scene_id: str,
    status: str,
    output: Any = None,
    output_schema: Optional[str] = None,
    config: Optional[dict] = None,
    error: Optional[str] = None,
) -> Checkpoint:
    """Convenience wrapper for scene-level checkpointing."""
    return self.save_checkpoint(
        stage=stage,
        pipeline_id=pipeline_id,
        scene_id=scene_id,
        status=status,
        output=output,
        output_schema=output_schema,
        config=config,
        error=error,
    )

def get_scene_status(
    self,
    pipeline_id: str,
    stage: str,
    scene_ids: list[str],
    config: Optional[dict] = None,
) -> dict[str, str]:
    """
    Get status of multiple scenes at once.
    Returns dict of {scene_id: "completed"|"pending"|"failed"}.
    """
    result = {}
    for sid in scene_ids:
        if self.is_completed(stage, pipeline_id, scene_id=sid, config=config):
            result[sid] = "completed"
        else:
            cp = self.load_checkpoint(stage, pipeline_id, scene_id=sid)
            result[sid] = cp.status if cp and cp.status == "failed" else "pending"
    return result
```

</action>

<acceptance_criteria>
- `save_scene_checkpoint()` delegates to `save_checkpoint()` with `scene_id` set
- `get_scene_status()` returns correct status for a batch of scene IDs
- Scene checkpoints saved to `data/checkpoints/{pipeline_id}/{stage}/{scene_id}.json`
- A scene returns "completed" only if its individual checkpoint exists and hash matches
</acceptance_criteria>

## Verification

1. `python -c "from agent_core.core.jobs import ActiveJobs; j=ActiveJobs(maxsize=3); j.add('a', JobInfo('a','running')); j.add('b', JobInfo('b','running')); j.add('c', JobInfo('c','running')); j.add('d', JobInfo('d','running')); assert len(j)==3; assert j.get('a') is None"` — exits 0 (LRU eviction works)
2. `python -c "import portalocker; print('OK')"` — exits 0
3. `python -c "from agent_core.core.quota import QuotaBudget; q=QuotaBudget(); q.consume('youtube_data', 1); print('OK')"` — exits 0 (portalocker in quota works)
4. Run concurrent `save_checkpoint()` calls from parallel threads — all writes succeed without corruption
5. Manual test: open `data/quota/budget.json` in editor, run `consume()` — exclusive lock prevents concurrent write corruption on platforms that support it

## Must Haves

- [ ] All state file operations (tracker, state_manager, quota, checkpoints) use `portalocker`
- [ ] `ActiveJobs` evicts LRU entries when `maxsize` is exceeded
- [ ] Scene-level checkpoints have convenience methods (`save_scene_checkpoint`, `get_scene_status`)
- [ ] Atomic writes (tmp + rename) used everywhere in addition to file locks
- [ ] `os.fsync()` called before releasing locks

## Must Nots

- [ ] Do NOT modify existing scraper or LLM client logic — locking only affects state files
- [ ] Do NOT change `ActiveJobs` maxsize at runtime (immutable after construction)
- [ ] Do NOT add distributed locking (single-machine only for v1)
