"""Audio — TTS provider abstraction, force alignment, subtitle generation, and temp asset lifecycle.

Sub-modules:
    tts             — Provider abstraction, fallback chain, config loading.
    script_splitter — Multi-scene script parsing.
    alignment       — Force alignment via faster-whisper.
    subtitles       — SRT and VTT subtitle generation.
    pipeline        — Per-scene audio production orchestrator.
    lifecycle       — Temp asset manifest tracking and cleanup.
"""

# TTS
from agent_core.audio.tts import (
    BaseTTSProvider,
    TTSResult,
    GeminiTTSProvider,
    GoogleCloudTTSProvider,
    EdgeTTSProvider,
    FallbackChain,
    PROVIDERS,
    DEFAULT_FALLBACK_CHAIN,
    _load_tts_config,
)

# Script splitter
from agent_core.audio.script_splitter import (
    split_script_text,
    split_script_from_json,
    write_scene_scripts,
    determine_source,
)

# Force alignment
from agent_core.audio.alignment import (
    force_align,
    force_align_scene,
    save_alignment,
)

# Subtitles
from agent_core.audio.subtitles import (
    generate_srt,
    generate_vtt,
    generate_subtitle_files,
)

# Pipeline orchestration
from agent_core.audio.pipeline import AudioPipeline, run_audio_pipeline

# Temp asset lifecycle
from agent_core.audio.lifecycle import TempAssetManifest, register_temp_cleanup

__all__ = [
    # TTS
    "BaseTTSProvider",
    "TTSResult",
    "GeminiTTSProvider",
    "GoogleCloudTTSProvider",
    "EdgeTTSProvider",
    "FallbackChain",
    "PROVIDERS",
    "DEFAULT_FALLBACK_CHAIN",
    "_load_tts_config",
    # Script splitter
    "split_script_text",
    "split_script_from_json",
    "write_scene_scripts",
    "determine_source",
    # Force alignment
    "force_align",
    "force_align_scene",
    "save_alignment",
    # Subtitles
    "generate_srt",
    "generate_vtt",
    "generate_subtitle_files",
    # Pipeline
    "AudioPipeline",
    "run_audio_pipeline",
    # Lifecycle
    "TempAssetManifest",
    "register_temp_cleanup",
]
