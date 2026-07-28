"""Force alignment — word-level timestamp extraction via faster-whisper with built-in VAD filtering."""

from agent_core.audio.alignment.aligner import (
    force_align,
    force_align_scene,
    save_alignment,
)

__all__ = [
    "force_align",
    "force_align_scene",
    "save_alignment",
]
