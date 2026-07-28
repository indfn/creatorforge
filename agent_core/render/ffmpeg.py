"""FFmpeg subprocess utilities for video rendering.

Centralises all FFmpeg/FFprobe invocations so scene rendering and assembly
code never call subprocess directly.
"""

import json
import logging
import subprocess
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FFmpegUtils:
    """Static FFmpeg/FFprobe helpers.

    All methods log warnings on failure and return safe fallback values
    rather than raising (consistent with project conventions).
    """

    @staticmethod
    def check_available() -> bool:
        """Verify that ``ffmpeg`` is installed and callable.

        Returns:
            ``True`` if ``ffmpeg -version`` succeeds, ``False`` otherwise.
        """
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            logger.warning("ffmpeg not found or not executable")
            return False

    @staticmethod
    def run(cmd: list[str], timeout: int = 300) -> Optional[subprocess.CompletedProcess]:
        """Run an FFmpeg command with logging and error handling.

        Args:
            cmd: Full ``ffmpeg`` argument list (including ``["ffmpeg", ...]``).
            timeout: Max seconds to wait (default 300).

        Returns:
            :class:`~subprocess.CompletedProcess` on success, or ``None`` on failure.
        """
        logger.debug("Running: %s", " ".join(str(c) for c in cmd))
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")[:500]
                logger.warning("FFmpeg exited %d: %s", result.returncode, stderr)
                return None
            return result
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            logger.warning("FFmpeg command failed: %s", exc)
            return None

    @staticmethod
    def video_info(path: Path) -> dict:
        """Probe a video file's metadata via ``ffprobe``.

        Args:
            path: Path to the video file.

        Returns:
            Dict with keys ``duration`` (float seconds), ``width``, ``height`` (int),
            ``codec`` (str), ``fps`` (float), or empty dict on failure.
        """
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=30, check=True)
            data = json.loads(result.stdout)
            info: dict = {}

            # Duration from format or first stream
            fmt = data.get("format", {})
            if "duration" in fmt:
                info["duration"] = float(fmt["duration"])

            # Stream details (take first video stream)
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    info["width"] = int(stream.get("width", 0))
                    info["height"] = int(stream.get("height", 0))
                    info["codec"] = stream.get("codec_name", "unknown")
                    # FPS from r_frame_rate string "num/den"
                    r_frame_rate = stream.get("r_frame_rate", "0/1")
                    match = re.match(r"(\d+)/(\d+)", r_frame_rate)
                    if match:
                        num, den = int(match.group(1)), int(match.group(2))
                        info["fps"] = round(num / den, 3) if den else 0.0
                    break

            return info
        except (subprocess.CalledProcessError, FileNotFoundError,
                json.JSONDecodeError, OSError, ValueError) as exc:
            logger.warning("Failed to probe video %s: %s", path, exc)
            return {}

    @staticmethod
    def scene_duration(path: Path) -> float:
        """Get the duration of a scene clip in seconds.

        Args:
            path: Path to the video file.

        Returns:
            Duration in seconds, or ``0.0`` on failure.
        """
        info = FFmpegUtils.video_info(path)
        return info.get("duration", 0.0)

    @staticmethod
    def scene_clip_from_frames(
        frame_dir: Path,
        output: Path,
        fps: int = 30,
        preset: str = "medium",
    ) -> Optional[Path]:
        """Compose a video clip from a directory of sequentially-named frames.

        Expects frames named ``frame_000001.png``, ``frame_000002.png``, etc.

        Args:
            frame_dir: Directory containing frame images.
            output: Output video path.
            fps: Output frame rate (default 30).
            preset: FFmpeg x264 preset (default ``"medium"``).

        Returns:
            ``output`` on success, or ``None`` on failure.
        """
        output.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-pattern_type", "glob",
            "-i", str(frame_dir / "*.png"),
            "-c:v", "libx264",
            "-preset", preset,
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output),
        ]
        result = FFmpegUtils.run(cmd)
        if result is None:
            return None
        return output

    @staticmethod
    def concat_clips(
        clip_paths: list[Path],
        output: Path,
    ) -> Optional[Path]:
        """Concatenate multiple video clips using the concat demuxer.

        All clips must share the same codec, resolution, and FPS.

        Args:
            clip_paths: Ordered list of clip file paths.
            output: Output concatenated video path.

        Returns:
            ``output`` on success, or ``None`` on failure.
        """
        if not clip_paths:
            logger.warning("No clips to concatenate")
            return None

        output.parent.mkdir(parents=True, exist_ok=True)

        concat_file = output.parent / "_concat_list.txt"
        try:
            concat_file.write_text(
                "\n".join(f"file '{p.resolve()}'" for p in clip_paths) + "\n",
                encoding="utf-8",
            )

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(output),
            ]
            result = FFmpegUtils.run(cmd)
            if result is None:
                return None
            return output
        finally:
            concat_file.unlink(missing_ok=True)

    @staticmethod
    def crossfade_assembly(
        clip_paths: list[Path],
        output: Path,
        transition_duration: float = 0.5,
    ) -> Optional[Path]:
        """Assemble clips with crossfade transitions via filter complex.

        Uses the ``xfade`` video filter between consecutive clips. Audio is
        crossfaded with ``acrossfade``.

        Args:
            clip_paths: Ordered list of scene clip paths.
            output: Output assembled video path.
            transition_duration: Crossfade duration in seconds (default 0.5).

        Returns:
            ``output`` on success, or ``None`` on failure.
        """
        if not clip_paths:
            logger.warning("No clips to assemble")
            return None

        if len(clip_paths) == 1:
            return FFmpegUtils.concat_clips(clip_paths, output)

        output.parent.mkdir(parents=True, exist_ok=True)

        # Build filter complex for crossfade between N clips
        # For N clips we need N-1 xfade transitions
        n = len(clip_paths)
        # Step 1: Get durations for offset calculation
        durations = []
        for p in clip_paths:
            d = FFmpegUtils.scene_duration(p)
            durations.append(d)

        # Calculate cumulative start times for each xfade offset
        # xfade position after clip_i = sum of durations[0:i+1] - transition_duration * (i)
        filter_parts = []
        inputs = []
        for i, clip in enumerate(clip_paths):
            inputs.extend(["-i", str(clip)])

        # If 2 clips, simple xfade
        if n == 2:
            d0 = durations[0] if durations[0] > 0 else 10.0
            offset = d0 - transition_duration
            filter_str = (
                f"[0:v][1:v]xfade=transition=fade:duration={transition_duration}:"
                f"offset={offset}[v];"
                f"[0:a][1:a]acrossfade=d={transition_duration}[a]"
            )
        else:
            # Build progressive xfade for 3+ clips
            segments = []
            for i in range(n - 1):
                seg_label = f"v{i}"
                if i == 0:
                    # First transition: [0:v][1:v]
                    d_prev = durations[0] if durations[0] > 0 else 10.0
                    offset = d_prev - transition_duration
                    segments.append(
                        f"[{i}:v][{i+1}:v]xfade=transition=fade:"
                        f"duration={transition_duration}:offset={offset}[{seg_label}]"
                    )
                else:
                    # Subsequent transitions: [v{i-1}][{i+1}:v]
                    d_prev = durations[i] if durations[i] > 0 else 10.0
                    # Calculate cumulative offset
                    cum_offset = sum(durations[:i+1]) - transition_duration * (i + 1)
                    offset = max(0, cum_offset)
                    prev_label = f"v{i-1}"
                    segments.append(
                        f"[{prev_label}][{i+1}:v]xfade=transition=fade:"
                        f"duration={transition_duration}:offset={offset}[{seg_label}]"
                    )

            # Audio crossfade chain
            audio_segments = []
            for i in range(n - 1):
                a_label = f"a{i}"
                if i == 0:
                    audio_segments.append(
                        f"[0:a][1:a]acrossfade=d={transition_duration}[{a_label}]"
                    )
                else:
                    prev_a = f"a{i-1}"
                    audio_segments.append(
                        f"[{prev_a}][{i+1}:a]acrossfade=d={transition_duration}[{a_label}]"
                    )

            filter_str = ";".join(segments + audio_segments)

        if n == 2:
            cmd = [
                "ffmpeg", "-y",
                "-i", str(clip_paths[0]),
                "-i", str(clip_paths[1]),
                "-filter_complex", filter_str,
                "-map", "[v]",
                "-map", "[a]",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-movflags", "+faststart",
                str(output),
            ]
        else:
            final_v_label = f"v{n-2}"
            final_a_label = f"a{n-2}"
            cmd = [
                "ffmpeg", "-y",
                *inputs,
                "-filter_complex", filter_str,
                "-map", f"[{final_v_label}]",
                "-map", f"[{final_a_label}]",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-movflags", "+faststart",
                str(output),
            ]

        result = FFmpegUtils.run(cmd)
        if result is None:
            return None
        return output

    @staticmethod
    def _escape_filter_path(path: Path) -> str:
        escaped = str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        return escaped

    @staticmethod
    def burn_subtitles(
        video_path: Path,
        subtitle_path: Path,
        output_path: Path,
    ) -> Optional[Path]:
        """Burn subtitles into a video using the FFmpeg subtitles filter.

        Args:
            video_path: Input video file.
            subtitle_path: SRT subtitle file.
            output_path: Output video file with burned-in subtitles.

        Returns:
            ``output_path`` on success, or ``None`` on failure.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", f"subtitles={FFmpegUtils._escape_filter_path(subtitle_path)}",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_path),
        ]
        result = FFmpegUtils.run(cmd)
        if result is None:
            return None
        return output_path

    @staticmethod
    def scale_crop(
        video_path: Path,
        output_path: Path,
        target_width: int,
        target_height: int,
    ) -> Optional[Path]:
        """Scale and centre-crop a video to target dimensions.

        Args:
            video_path: Input video file.
            output_path: Output resized video path.
            target_width: Target width in pixels.
            target_height: Target height in pixels.

        Returns:
            ``output_path`` on success, or ``None`` on failure.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Scale to fill target dimensions, then centre-crop
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf",
            f"scale={target_width}:{target_height}:force_original_aspect_ratio=1,"
            f"crop={target_width}:{target_height}",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-movflags", "+faststart",
            str(output_path),
        ]
        result = FFmpegUtils.run(cmd)
        if result is None:
            return None
        return output_path
