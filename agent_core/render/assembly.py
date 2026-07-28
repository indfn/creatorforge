"""Scene clip assembly, subtitle overlay, and multi-format output.

Assembles rendered scene clips into a final video with crossfade transitions,
burns in SRT/VTT subtitle tracks, and produces multi-format outputs
(16:9, 9:16, 1:1).
"""

import logging
import re
import shutil
from pathlib import Path
from typing import Optional

from agent_core.render.ffmpeg import FFmpegUtils

logger = logging.getLogger(__name__)

FORMAT_PRESETS: dict[str, tuple[int, int]] = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
}


class AssemblyEngine:
    """Assembles rendered scene clips into final video with transitions,
    subtitles, and multi-format output.
    """

    def __init__(self, channel_config: dict, production_dir: Path):
        self.channel_config = channel_config
        self.production_dir = Path(production_dir)
        self.render_config = channel_config.get("render", {})

    def assemble_scenes(
        self,
        scene_clips: list[dict],
        output_path: Path,
    ) -> Optional[Path]:
        if not scene_clips:
            logger.warning("No scene clips to assemble")
            return None

        output_path.parent.mkdir(parents=True, exist_ok=True)
        clip_paths = [Path(c["clip_path"]) for c in scene_clips]
        transition_duration = self.render_config.get("transition_duration", 0.5)

        if len(clip_paths) == 1:
            logger.info("Single scene — copying to master without transitions")
            return FFmpegUtils.concat_clips(clip_paths, output_path)

        logger.info(
            "Assembling %d clips with %.1fs crossfade",
            len(clip_paths),
            transition_duration,
        )
        return FFmpegUtils.crossfade_assembly(
            clip_paths, output_path, transition_duration,
        )

    def burn_subtitles(
        self,
        video_path: Path,
        subtitle_paths: dict[str, Path],
        output_path: Path,
    ) -> Optional[Path]:
        if not subtitle_paths:
            logger.info("No subtitles to burn")
            shutil.copy2(video_path, output_path)
            return output_path

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if len(subtitle_paths) == 1:
            srt_path = list(subtitle_paths.values())[0]
            return FFmpegUtils.burn_subtitles(video_path, srt_path, output_path)

        combined_srt = self._combine_subtitles(subtitle_paths)
        return FFmpegUtils.burn_subtitles(video_path, combined_srt, output_path)

    @staticmethod
    def _offset_srt(srt_path: Path, offset_seconds: float) -> str:
        """Offset all subtitle timestamps in an SRT by the given seconds."""
        lines = srt_path.read_text(encoding="utf-8")
        def _offset_timestamp(match):
            ts = match.group(0)
            parts = re.split(r"[:,]", ts)
            h, m, s, ms = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
            total_ms = int((h * 3600 + m * 60 + s + offset_seconds) * 1000) + ms
            total_ms = max(0, total_ms)
            new_h = total_ms // 3600000
            total_ms %= 3600000
            new_m = total_ms // 60000
            total_ms %= 60000
            new_s = total_ms // 1000
            new_ms = total_ms % 1000
            return f"{new_h:02d}:{new_m:02d}:{new_s:02d},{new_ms:03d}"
        ts_pattern = r"\d{2}:\d{2}:\d{2},\d{3}"
        return re.sub(ts_pattern, _offset_timestamp, lines)

    def _combine_subtitles(self, subtitle_paths: dict[str, Path]) -> Path:
        """Combine per-scene SRT files into one, offsetting each by scene start."""
        output = self.production_dir / "render" / "combined_subtitles.srt"
        output.parent.mkdir(parents=True, exist_ok=True)

        combined_lines = []
        entry_counter = 1
        current_offset = 0.0

        for scene_id in sorted(subtitle_paths.keys()):
            srt_path = subtitle_paths[scene_id]
            if not srt_path.exists():
                logger.warning("Subtitle file not found: %s", srt_path)
                continue

            offset_content = self._offset_srt(srt_path, current_offset)
            lines = offset_content.strip().split("\n")
            for line in lines:
                if line.strip().isdigit():
                    combined_lines.append(str(entry_counter))
                    entry_counter += 1
                else:
                    combined_lines.append(line)

            scene_duration = self._get_scene_duration(scene_id)
            current_offset += scene_duration

        output.write_text("\n".join(combined_lines) + "\n", encoding="utf-8")
        return output

    def _get_scene_duration(self, scene_id: str) -> float:
        """Get the duration of a rendered scene clip."""
        clip_path = self.production_dir / "render" / "scenes" / f"{scene_id}.mp4"
        if clip_path.exists():
            return FFmpegUtils.scene_duration(clip_path)
        return 10.0

    def generate_formats(
        self,
        master_path: Path,
        output_dir: Path,
        formats: Optional[list[str]] = None,
    ) -> dict[str, Optional[Path]]:
        if formats is None:
            formats = self.render_config.get("output_formats", ["16:9"])

        results: dict[str, Optional[Path]] = {}
        output_dir = output_dir / "final"

        for fmt in formats:
            if fmt not in FORMAT_PRESETS:
                logger.warning("Unknown format %r — skipping", fmt)
                continue

            target_w, target_h = FORMAT_PRESETS[fmt]
            fmt_dir = output_dir / fmt.replace(":", "x")
            fmt_dir.mkdir(parents=True, exist_ok=True)
            output_path = fmt_dir / "output.mp4"

            if fmt == "16:9":
                shutil.copy2(master_path, output_path)
                results[fmt] = output_path
                logger.info("Copied master for 16:9 format")
            else:
                result = FFmpegUtils.scale_crop(master_path, output_path, target_w, target_h)
                results[fmt] = result
                if result:
                    logger.info("Generated %s format: %s", fmt, output_path)
                else:
                    logger.warning("Failed to generate %s format", fmt)

        return results
