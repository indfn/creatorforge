"""
SQLite-backed transcript cache for the Content Skeleton Ripper.

Replaces the flat-file TranscriptCache with a persistent, TTL-aware
SQLite database. Thread-safe via threading.Lock.
"""

__all__ = ["DbTranscriptCache", "migrate_from_flat_cache"]
