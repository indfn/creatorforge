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
    status: str
    stage: str = ""
    progress: float = 0.0
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
