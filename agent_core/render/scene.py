"""Per-scene two-pass render: HyperFrames HTML blueprint assembly → Playwright → FFmpeg scene clip.

Each blueprint is a proper HyperFrames composition with GSAP timeline,
compatible with npx hyperframes {lint,validate,preview,render}.
"""

from html import escape
import json
import logging
import re
from pathlib import Path
from typing import Optional

from agent_core.render.ffmpeg import FFmpegUtils

logger = logging.getLogger(__name__)


# =========================================================================
# HyperFrames HTML blueprint generation (per-scene)
# =========================================================================

GSAP_CDN = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"

_BASE_CSS = """\
* { margin: 0; padding: 0; box-sizing: border-box; }
body { margin: 0; overflow: hidden; }
#root {
  position: relative;
  overflow: hidden;
}
.clip {
  position: absolute;
  inset: 0;
}
.text-element {
  display: grid;
  place-items: center;
  font-family: system-ui, -apple-system, sans-serif;
  font-weight: 700;
  font-size: 3rem;
  color: #fff;
  text-shadow: 0 2px 10px rgba(0,0,0,0.5);
  padding: 2rem;
}
.image-element {
  display: grid;
  place-items: center;
}
.image-element img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
.broll-element {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
"""


def _generate_scene_blueprint(
    scene_id: str,
    timeline: dict,
    channel_config: dict,
) -> str:
    """Generate a HyperFrames-compliant HTML blueprint for a single scene.

    Produces a standalone (top-level) composition with:
      - Root ``<div>`` with ``data-composition-id``, ``data-width``,
        ``data-height``, ``data-duration``
      - Each timeline element as a ``<section class="clip">`` with
        ``data-start``, ``data-duration``, ``data-track-index``, ``id``
      - A paused GSAP timeline registered at
        ``window.__timelines["scene-{scene_id}"]`` with seekable tweens

    Args:
        scene_id: Scene identifier (e.g. ``"scene_01"``).
        timeline: Scene timeline dict with ``duration`` and ``elements``.
        channel_config: Channel configuration dict with render params.

    Returns:
        Inline HTML string compatible with ``npx hyperframes validate``.
    """
    width = channel_config.get("render", {}).get("width", 1920)
    height = channel_config.get("render", {}).get("height", 1080)
    total_duration = timeline.get("duration", 10.0)
    elements = timeline.get("elements", [])

    clips_html = ""
    tweens_js = ""
    for idx, el in enumerate(elements):
        el_type = el.get("type", "text")
        el_content = el.get("content", "")
        el_start = el.get("start", 0.0)
        el_duration = el.get("duration", total_duration)
        el_id = f"el-{idx}"

        if el_type == "text":
            clips_html += (
                f'    <section id="{el_id}" class="clip text-element"'
                f' data-start="{el_start}" data-duration="{el_duration}"'
                f' data-track-index="1">{escape(el_content)}</section>\n'
            )
            tweens_js += (
                f'  tl.from("#{el_id}",'
                f' {{ opacity: 0, y: 48, duration: 0.6, ease: "power3.out" }},'
                f" {el_start});\n"
            )

        elif el_type == "image":
            src = el.get("src", "")
            clips_html += (
                f'    <section id="{el_id}" class="clip image-element"'
                f' data-start="{el_start}" data-duration="{el_duration}"'
                f' data-track-index="1">\n'
                f'      <img src="{escape(src, quote=True)}" alt="">\n'
                f"    </section>\n"
            )
            tweens_js += (
                f'  tl.from("#{el_id}",'
                f' {{ opacity: 0, scale: 0.9, duration: 0.5,'
                f' ease: "power2.out" }},'
                f" {el_start});\n"
            )

        elif el_type == "broll":
            broll_path = el.get("path", "")
            clips_html += (
                f'    <video id="{el_id}" class="broll-element"'
                f' data-start="{el_start}" data-duration="{el_duration}"'
                f' data-track-index="0"'
                f' src="{escape(broll_path, quote=True)}"'
                f' muted playsinline></video>\n'
            )
            tweens_js += (
                f'  tl.from("#{el_id}",'
                f' {{ opacity: 0, duration: 0.4, ease: "power1.out" }},'
                f" {el_start});\n"
            )

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={width},height={height}">
<title>Scene {escape(scene_id)}</title>
<script src="{GSAP_CDN}"></script>
<style>
  body {{ width: {width}px; height: {height}px; background: #1a1a2e; }}
  #root {{ width: {width}px; height: {height}px; background: #1a1a2e; }}
{_BASE_CSS}
</style>
</head>
<body>
<div id="root"
     data-composition-id="scene-{scene_id}"
     data-width="{width}"
     data-height="{height}"
     data-duration="{total_duration}">
{clips_html}</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
{tweens_js}window.__timelines["scene-{scene_id}"] = tl;
</script>
</body>
</html>"""
    return html


# =========================================================================
# Per-scene render
# =========================================================================


def render_scene(
    scene_id: str,
    production_dir: Path,
    channel_config: dict,
    timeline: dict,
) -> Optional[Path]:
    """Render a single scene: HyperFrames HTML → Playwright → MP4 clip.

    Two-pass:
      1. Generate a HyperFrames-compliant HTML blueprint (``_generate_scene_blueprint``).
      2. Render via Playwright headless Chromium (video recording).

    Args:
        scene_id: Scene identifier (e.g. ``"scene_01"``).
        production_dir: Active production directory.
        channel_config: Channel configuration dict.
        timeline: Scene timeline dict with elements, duration, audio refs.

    Returns:
        Path to rendered ``.mp4`` clip, or ``None`` on failure.
    """
    blueprint_dir = production_dir / "render" / "blueprints"
    scene_dir = production_dir / "render" / "scenes"
    blueprint_dir.mkdir(parents=True, exist_ok=True)
    scene_dir.mkdir(parents=True, exist_ok=True)

    html = _generate_scene_blueprint(scene_id, timeline, channel_config)
    blueprint_path = blueprint_dir / f"{scene_id}.html"
    blueprint_path.write_text(html, encoding="utf-8")
    logger.info("Blueprint written: %s", blueprint_path)

    output_path = scene_dir / f"{scene_id}.mp4"

    try:
        _render_with_playwright(blueprint_path, output_path, channel_config)
        if output_path.exists() and output_path.stat().st_size > 0:
            logger.info("Scene rendered: %s", output_path)
            return output_path

        logger.warning("Scene render produced empty output for %s", scene_id)
        return None

    except Exception as exc:
        logger.warning("Scene render failed for %s: %s", scene_id, exc)
        return None


def _render_with_playwright(
    blueprint_path: Path,
    output_path: Path,
    channel_config: dict,
) -> None:
    """Render a HyperFrames HTML blueprint to video using Playwright.

    Loads the composition, starts the GSAP timeline and any video elements,
    then records via Playwright's built-in video capture.

    Args:
        blueprint_path: Path to the HTML blueprint file.
        output_path: Desired output video path.
        channel_config: Channel configuration with render params.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning(
            "playwright not installed — install with: "
            "pip install playwright && playwright install chromium"
        )
        return

    width = channel_config.get("render", {}).get("width", 1920)
    height = channel_config.get("render", {}).get("height", 1080)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height},
            record_video_dir=str(output_path.parent),
            record_video_size={"width": width, "height": height},
        )
        page = context.new_page()
        page.goto(f"file://{blueprint_path.resolve()}")

        page.wait_for_function(
            "typeof gsap !== 'undefined' && window.__timelines && "
            "Object.keys(window.__timelines).length > 0",
            timeout=15000,
        )

        comp_id = page.evaluate(
            "document.querySelector('[data-composition-id]')"
            ".getAttribute('data-composition-id')"
        )

        page.evaluate("""
            const tl = window.__timelines[arguments[0]];
            if (tl) tl.play();
            document.querySelectorAll('video').forEach(v => {
                v.play().catch(() => {});
            });
        """, comp_id)

        duration = _estimate_scene_duration(blueprint_path)
        wait_ms = int((duration + 1.0) * 1000)
        page.wait_for_timeout(wait_ms)

        context.close()
        browser.close()

    video_dir = output_path.parent
    video_files = sorted(video_dir.glob("*.webm"))
    if video_files:
        webm_path = video_files[-1]
        FFmpegUtils.run([
            "ffmpeg", "-y",
            "-i", str(webm_path),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_path),
        ])
        webm_path.unlink(missing_ok=True)


def _estimate_scene_duration(blueprint_path: Path) -> float:
    """Read scene duration from the HyperFrames ``data-duration`` attribute.

    Args:
        blueprint_path: Path to the HTML blueprint file.

    Returns:
        Duration in seconds, defaulting to 10.0.
    """
    try:
        html = blueprint_path.read_text(encoding="utf-8")
        match = re.search(r'data-duration="([\d.]+)"', html)
        if match:
            return float(match.group(1))
    except (OSError, ValueError):
        pass
    return 10.0
