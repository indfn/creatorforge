"""Scene Assembly & Final Render pipeline.

Transforms per-scene assets (audio, subtitles, B-roll, character SVGs, annotated
scripts) into publishable video via HyperFrames HTML blueprints, Puppeteer scene
rendering, and FFmpeg final assembly with crossfade transitions and multi-format
output.
"""

from agent_core.render.ffmpeg import FFmpegUtils
from agent_core.render.scene import render_scene
from agent_core.render.assembly import AssemblyEngine
from agent_core.render.pipeline import RenderPipeline, run_render_pipeline

__all__ = [
    "FFmpegUtils",
    "render_scene",
    "AssemblyEngine",
    "RenderPipeline",
    "run_render_pipeline",
]
