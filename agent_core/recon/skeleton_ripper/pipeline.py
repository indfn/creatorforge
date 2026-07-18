"""
Main pipeline orchestration for Content Skeleton Ripper.
Ported from ReelRecon — uses InstaClient instead of cookie-based session.
"""

import os
import json
import uuid
import time
import traceback
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable
from enum import Enum

from .cache import is_valid_transcript
from .llm_client import LLMClient
from .extractor import BatchedExtractor
from .aggregator import SkeletonAggregator, AggregatedData
from .synthesizer import PatternSynthesizer, SynthesisResult, generate_report
from agent_core.recon.utils.logger import get_logger
from agent_core.recon.cache.db_cache import DbTranscriptCache, migrate_from_flat_cache
from agent_core.recon.skeleton_ripper.cleaning import clean_transcript
from agent_core.recon.scraper.youtube import get_video_captions
from agent_core.recon.scraper.youtube import download_video as _yt_download_video

# Import recon scrapers (replaces ReelRecon's cookie-based scraper)
from agent_core.recon.scraper.instagram import InstaClient
from agent_core.recon.scraper.downloader import (
    transcribe_video,
    transcribe_video_local,
    load_whisper_model,
    download_direct,
    WHISPER_AVAILABLE,
)
from agent_core.recon.config import load_config

logger = get_logger()

RECON_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "recon"


class JobStatus(Enum):
    PENDING = "pending"
    SCRAPING = "scraping"
    TRANSCRIBING = "transcribing"
    EXTRACTING = "extracting"
    AGGREGATING = "aggregating"
    SYNTHESIZING = "synthesizing"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class JobProgress:
    status: JobStatus = JobStatus.PENDING
    phase: str = ""
    message: str = ""
    videos_scraped: int = 0
    videos_downloaded: int = 0
    videos_transcribed: int = 0
    transcripts_from_cache: int = 0
    valid_transcripts: int = 0
    skeletons_extracted: int = 0
    total_target: int = 0
    current_creator: str = ""
    current_creator_index: int = 0
    total_creators: int = 0
    reels_fetched: int = 0
    current_video_index: int = 0
    extraction_batch: int = 0
    extraction_total_batches: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    errors: list[str] = field(default_factory=list)


@dataclass
class JobConfig:
    usernames: list[str]
    videos_per_creator: int = 3
    platform: str = "instagram"
    llm_provider: str = "custom"
    llm_model: str = "gpt-4o-mini"
    min_valid_ratio: float = 0.6
    transcribe_provider: str = "groq"
    whisper_model: str = "small.en"
    openai_api_key: Optional[str] = None
    transcribe_api_key: Optional[str] = None
    transcribe_base_url: str = ""
    transcribe_model: str = "whisper-large-v3-turbo"
    target_language: str = "en"


@dataclass
class JobResult:
    job_id: str
    success: bool
    config: JobConfig
    progress: JobProgress
    skeletons: list[dict] = field(default_factory=list)
    aggregated: Optional[AggregatedData] = None
    synthesis: Optional[SynthesisResult] = None
    report_path: Optional[str] = None
    skeletons_path: Optional[str] = None
    synthesis_path: Optional[str] = None


class SkeletonRipperPipeline:
    """
    Main pipeline — uses InstaClient (Instaloader) for IG scraping.
    """

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            base_dir = str(RECON_DATA_DIR)
        self.base_dir = Path(base_dir)
        self.output_dir = RECON_DATA_DIR / 'reports'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache = DbTranscriptCache()
        self._migrate_if_empty()
        logger.info("PIPELINE", f"SkeletonRipperPipeline initialized")

    def _migrate_if_empty(self):
        """Migrate flat cache to SQLite on first use (best-effort, silent)."""
        try:
            stats = self.cache.get_stats()
            if stats.get('total_transcripts', 0) == 0:
                from .cache import CACHE_DIR
                migrated, total = migrate_from_flat_cache(str(CACHE_DIR), self.cache)
                if migrated > 0:
                    logger.info("PIPELINE", f"Migrated {migrated}/{total} flat cache entries to SQLite")
        except Exception:
            pass  # Migration is best-effort

    def run(self, config: JobConfig, on_progress: Optional[Callable[[JobProgress], None]] = None) -> JobResult:
        job_id = f"sr_{uuid.uuid4().hex[:8]}"
        progress = JobProgress(
            status=JobStatus.PENDING,
            started_at=datetime.utcnow().isoformat(),
            total_target=len(config.usernames) * config.videos_per_creator,
            total_creators=len(config.usernames)
        )
        result = JobResult(job_id=job_id, success=False, config=config, progress=progress)

        try:
            llm_client = LLMClient(provider=config.llm_provider, model=config.llm_model)

            # Stage 1: Scrape and transcribe
            progress.status = JobStatus.SCRAPING
            progress.phase = "Scraping videos..."
            self._notify(on_progress, progress)

            transcripts = self._scrape_and_transcribe(config=config, progress=progress, on_progress=on_progress)

            valid_count = sum(1 for t in transcripts if is_valid_transcript(t.get('transcript', '')))
            progress.valid_transcripts = valid_count

            if valid_count == 0:
                raise ValueError("No valid transcripts to process")

            valid_transcripts = [t for t in transcripts if is_valid_transcript(t.get('transcript', ''))]

            # Stage 2: Extraction
            progress.status = JobStatus.EXTRACTING
            progress.phase = "Extracting content skeletons..."
            self._notify(on_progress, progress)

            extractor = BatchedExtractor(llm_client)
            extraction_result = extractor.extract_all(
                valid_transcripts,
                on_progress=lambda done, total, batch, total_batches: self._update_extraction_progress(
                    progress, done, total, batch, total_batches, on_progress
                )
            )
            result.skeletons = extraction_result.successful
            progress.skeletons_extracted = len(extraction_result.successful)

            if not result.skeletons:
                raise ValueError("No skeletons extracted successfully")

            # Stage 3: Aggregation
            progress.status = JobStatus.AGGREGATING
            progress.phase = "Aggregating patterns..."
            self._notify(on_progress, progress)

            aggregator = SkeletonAggregator()
            result.aggregated = aggregator.aggregate(result.skeletons)

            # Stage 4: Synthesis
            progress.status = JobStatus.SYNTHESIZING
            progress.phase = "Synthesizing content strategy..."
            self._notify(on_progress, progress)

            synthesizer = PatternSynthesizer(llm_client)
            result.synthesis = synthesizer.synthesize(result.aggregated)

            # Stage 5: Output
            output_paths = self._save_outputs(job_id, config, result)
            result.report_path = output_paths.get('report')
            result.skeletons_path = output_paths.get('skeletons')
            result.synthesis_path = output_paths.get('synthesis')

            progress.status = JobStatus.COMPLETE
            progress.phase = "Analysis Complete"
            progress.message = f"Done: {len(result.skeletons)} skeletons from {len(config.usernames)} creator(s)"
            progress.completed_at = datetime.utcnow().isoformat()
            result.success = True

        except Exception as e:
            logger.error("SKELETON", f"Pipeline failed: {e}")
            progress.status = JobStatus.FAILED
            progress.phase = "Failed"
            progress.errors.append(str(e))
            progress.completed_at = datetime.utcnow().isoformat()

        self._notify(on_progress, progress)
        return result

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _make_transcript_entry(video: dict, transcript: str,
                                from_cache: bool = False,
                                source: str = "whisper_api") -> dict:
        """Build a standardised transcript entry dict."""
        return {
            'video_id': video.get('video_id') or video.get('shortcode', ''),
            'username': video.get('username') or video.get('channel', ''),
            'platform': video.get('platform', 'youtube'),
            'views': video.get('views', 0),
            'likes': video.get('likes', 0),
            'url': video.get('url', ''),
            'video_url': video.get('video_url', ''),
            'transcript': transcript,
            'from_cache': from_cache,
            'transcript_source': source,
        }

    def _download_and_transcribe(self, video: dict, config: JobConfig, username: str,
                                   platform: str, progress: JobProgress,
                                   on_progress: Optional[Callable],
                                   insta_client=None) -> Optional[str]:
        """Download a single video and transcribe it. Shared by YT and IG paths."""
        temp_dir = RECON_DATA_DIR / 'temp'
        temp_dir.mkdir(parents=True, exist_ok=True)

        video_id = video.get('video_id') or video.get('shortcode', '')
        video_path = temp_dir / f"{username}_{video_id}.mp4"
        views_display = f"{video.get('views', 0):,}"

        # ── Download ──
        progress.message = f"Downloading ({views_display} views)"
        self._notify(on_progress, progress)

        downloaded = False
        if platform == 'youtube':
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            downloaded = _yt_download_video(video_url, video_path, max_retries=2)
        else:
            video_url = video.get('video_url', '')
            if video_url:
                downloaded = download_direct(video_url, video_path)
            if not downloaded and insta_client:
                downloaded = insta_client.download_reel(video_id, video_path)

        if not downloaded or not video_path.exists():
            logger.warning("PIPELINE", f"Download failed for {platform}/{username}/{video_id}")
            return None

        progress.videos_downloaded += 1

        # ── Transcribe ──
        progress.message = f"Transcribing ({views_display} views)"
        self._notify(on_progress, progress)

        openai_key = config.openai_api_key or os.getenv('OPENAI_API_KEY') or os.getenv('LLM_API_KEY')
        transcribe_key = config.transcribe_api_key or openai_key

        transcript_text = None
        if config.transcribe_provider == 'groq' and transcribe_key:
            base_url = config.transcribe_base_url or os.getenv('TRANSCRIBE_BASE_URL', 'https://api.groq.com/openai/v1')
            transcript_text = transcribe_video(
                str(video_path),
                api_key=transcribe_key,
                base_url=base_url,
                model=config.transcribe_model or 'whisper-large-v3-turbo',
            )
        elif config.transcribe_provider == 'openai' and openai_key:
            base_url = config.transcribe_base_url or os.getenv('TRANSCRIBE_BASE_URL', 'https://api.openai.com/v1')
            transcript_text = transcribe_video(
                str(video_path),
                api_key=transcribe_key,
                base_url=base_url,
                model=config.transcribe_model or 'whisper-1',
            )
        elif config.transcribe_provider == 'local' and WHISPER_AVAILABLE:
            wm = load_whisper_model(config.whisper_model)
            if wm:
                transcript_text = transcribe_video_local(str(video_path), wm)

        # Cleanup temp video file
        try:
            if video_path.exists():
                video_path.unlink()
        except OSError:
            pass

        return transcript_text

    # ── Per-platform processing ──────────────────────────────────

    def _process_youtube(self, config: JobConfig, progress: JobProgress,
                          on_progress: Optional[Callable]) -> list[dict]:
        """Process YouTube competitors — caption-first, then download+transcribe fallback."""
        from agent_core.recon.scraper.youtube import get_channel_videos
        transcripts = []

        for idx, username in enumerate(config.usernames):
            progress.current_creator = username
            progress.current_creator_index = idx + 1
            progress.current_video_index = 0
            progress.phase = f"YouTube @{username} ({idx + 1}/{len(config.usernames)})"
            progress.message = "Checking cache..."
            self._notify(on_progress, progress)

            videos = get_channel_videos(username, max_videos=config.videos_per_creator * 3)
            if not videos:
                progress.errors.append(f"YouTube @{username}: No videos found")
                continue

            progress.videos_scraped += len(videos)
            valid_count = 0

            for video in videos:
                if valid_count >= config.videos_per_creator:
                    break

                video_id = video.get('video_id', '')

                # 1. Cache check
                cached = self.cache.get('youtube', username, video_id)
                if cached and is_valid_transcript(cached):
                    entry = self._make_transcript_entry(video, cached, from_cache=True)
                    transcripts.append(entry)
                    valid_count += 1
                    progress.transcripts_from_cache += 1
                    progress.videos_transcribed += 1
                    continue

                # 2. Caption-first (primary language)
                lang = config.target_language or 'en'
                caption_text = get_video_captions(video_id, lang=lang)
                if caption_text and is_valid_transcript(caption_text):
                    self.cache.set('youtube', username, video_id, caption_text,
                                   source='youtube_caption', language=lang)
                    entry = self._make_transcript_entry(video, caption_text, source='youtube_caption')
                    transcripts.append(entry)
                    valid_count += 1
                    progress.videos_transcribed += 1
                    continue

                # 3. Caption fallback: try English if primary != English
                if lang != 'en':
                    caption_text = get_video_captions(video_id, lang='en')
                    if caption_text and is_valid_transcript(caption_text):
                        self.cache.set('youtube', username, video_id, caption_text,
                                       source='youtube_caption', language='en')
                        entry = self._make_transcript_entry(video, caption_text, source='youtube_caption')
                        transcripts.append(entry)
                        valid_count += 1
                        progress.videos_transcribed += 1
                        continue

                # 4. Fallback: download + transcribe
                transcript_text = self._download_and_transcribe(
                    video, config, username, 'youtube', progress, on_progress,
                )
                if transcript_text and is_valid_transcript(transcript_text):
                    self.cache.set('youtube', username, video_id, transcript_text,
                                   source='whisper_api')
                    entry = self._make_transcript_entry(video, transcript_text, source='whisper_api')
                    transcripts.append(entry)
                    valid_count += 1
                    progress.videos_transcribed += 1

            if valid_count < config.videos_per_creator:
                progress.errors.append(
                    f"YouTube @{username}: Only {valid_count}/{config.videos_per_creator} valid transcripts"
                )

        return transcripts

    def _process_instagram(self, config: JobConfig, progress: JobProgress,
                            on_progress: Optional[Callable]) -> list[dict]:
        """Process Instagram competitors — cache → caption-as-transcript → download+transcribe."""
        transcripts = []

        # Build InstaClient once
        insta_client = None
        recon_config = load_config()
        if recon_config.ig_username and recon_config.ig_password:
            insta_client = InstaClient()
            if not insta_client.login(recon_config.ig_username, recon_config.ig_password):
                logger.error("PIPELINE", "Instagram login failed")
                progress.errors.append("Instagram login failed")
                return transcripts
        else:
            progress.errors.append("IG credentials not configured")
            return transcripts

        for idx, username in enumerate(config.usernames):
            progress.current_creator = username
            progress.current_creator_index = idx + 1
            progress.current_video_index = 0
            progress.phase = f"Instagram @{username} ({idx + 1}/{len(config.usernames)})"
            progress.message = "Fetching reels..."
            self._notify(on_progress, progress)

            reels = insta_client.get_competitor_reels(username, max_reels=100)
            if not reels:
                progress.errors.append(f"Instagram @{username}: No reels found")
                continue

            progress.videos_scraped += len(reels)
            progress.reels_fetched = len(reels)
            valid_count = 0

            for reel in reels:
                if valid_count >= config.videos_per_creator:
                    break

                video_id = reel.get('shortcode', 'unknown')
                platform = 'instagram'

                # 1. Cache check
                cached_text = self.cache.get(platform, username, video_id)
                if cached_text and is_valid_transcript(cached_text):
                    entry = self._make_transcript_entry(reel, cached_text, from_cache=True)
                    transcripts.append(entry)
                    valid_count += 1
                    progress.transcripts_from_cache += 1
                    progress.videos_transcribed += 1
                    continue

                # 2. Caption-as-transcript (D-05, D-06)
                caption = reel.get('caption', '')
                if caption and is_valid_transcript(caption, min_words=10):
                    self.cache.set(platform, username, video_id, caption,
                                   source='instagram_caption', language=config.target_language or 'en')
                    entry = self._make_transcript_entry(reel, caption, source='instagram_caption')
                    transcripts.append(entry)
                    valid_count += 1
                    progress.videos_transcribed += 1
                    continue

                # 3. Fallback: download + transcribe
                transcript_text = self._download_and_transcribe(
                    reel, config, username, 'instagram', progress, on_progress,
                    insta_client=insta_client,
                )
                if transcript_text and is_valid_transcript(transcript_text):
                    self.cache.set(platform, username, video_id, transcript_text,
                                   source='whisper_api')
                    entry = self._make_transcript_entry(reel, transcript_text, source='whisper_api')
                    transcripts.append(entry)
                    valid_count += 1
                    progress.videos_transcribed += 1

            if valid_count < config.videos_per_creator:
                progress.errors.append(
                    f"Instagram @{username}: Only {valid_count}/{config.videos_per_creator} valid transcripts"
                )

        return transcripts

    def _scrape_and_transcribe(self, config: JobConfig, progress: JobProgress,
                                on_progress: Optional[Callable]) -> list[dict]:
        """Delegate scraping+transcription to per-platform methods."""
        all_transcripts = []
        all_transcripts.extend(self._process_youtube(config, progress, on_progress))
        all_transcripts.extend(self._process_instagram(config, progress, on_progress))
        return all_transcripts

    def _update_extraction_progress(self, progress, done, total, batch, total_batches, on_progress):
        progress.skeletons_extracted = done
        progress.extraction_batch = batch
        progress.extraction_total_batches = total_batches
        progress.message = f"Extracting: batch {batch}/{total_batches} ({done}/{total} done)"
        self._notify(on_progress, progress)

    def _notify(self, callback, progress):
        if callback:
            try:
                callback(progress)
            except Exception:
                pass

    def _save_outputs(self, job_id: str, config: JobConfig, result: JobResult) -> dict[str, str]:
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        job_dir = self.output_dir / f"{timestamp}_{job_id}"
        job_dir.mkdir(parents=True, exist_ok=True)
        paths = {}

        skeletons_path = job_dir / 'skeletons.json'
        with open(skeletons_path, 'w', encoding='utf-8') as f:
            json.dump(result.skeletons, f, indent=2, default=str)
        paths['skeletons'] = str(skeletons_path)

        if result.synthesis:
            synthesis_path = job_dir / 'synthesis.json'
            with open(synthesis_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'success': result.synthesis.success,
                    'analysis': result.synthesis.analysis,
                    'templates': result.synthesis.templates,
                    'quick_wins': result.synthesis.quick_wins,
                    'warnings': result.synthesis.warnings,
                    'model_used': result.synthesis.model_used,
                    'synthesized_at': result.synthesis.synthesized_at
                }, f, indent=2)
            paths['synthesis'] = str(synthesis_path)

        if result.aggregated and result.synthesis:
            report_path = job_dir / 'report.md'
            report_content = generate_report(
                data=result.aggregated, synthesis=result.synthesis,
                job_config=asdict(config)
            )
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            paths['report'] = str(report_path)

        return paths


def create_job_config(
    usernames: list[str], videos_per_creator: int = 3, platform: str = "instagram",
    llm_provider: str = "custom", llm_model: str = "gpt-4o-mini",
    transcribe_provider: str = "groq", whisper_model: str = "small.en",
    openai_api_key: Optional[str] = None,
    transcribe_api_key: Optional[str] = None,
    transcribe_base_url: str = "",
    transcribe_model: str = "whisper-large-v3-turbo",
    target_language: str = "en",
) -> JobConfig:
    return JobConfig(
        usernames=usernames, videos_per_creator=videos_per_creator,
        platform=platform, llm_provider=llm_provider, llm_model=llm_model,
        transcribe_provider=transcribe_provider, whisper_model=whisper_model,
        openai_api_key=openai_api_key,
        transcribe_api_key=transcribe_api_key,
        transcribe_base_url=transcribe_base_url,
        transcribe_model=transcribe_model,
        target_language=target_language,
    )


def run_skeleton_ripper(
    usernames: list[str], videos_per_creator: int = 3, platform: str = "instagram",
    llm_provider: str = "custom", llm_model: str = "gpt-4o-mini",
    transcribe_provider: str = "groq", whisper_model: str = "small.en",
    openai_api_key: Optional[str] = None,
    transcribe_api_key: Optional[str] = None,
    transcribe_base_url: str = "",
    transcribe_model: str = "whisper-large-v3-turbo",
    target_language: str = "en",
    on_progress: Optional[Callable] = None
) -> JobResult:
    config = create_job_config(
        usernames=usernames, videos_per_creator=videos_per_creator,
        platform=platform, llm_provider=llm_provider, llm_model=llm_model,
        transcribe_provider=transcribe_provider, whisper_model=whisper_model,
        openai_api_key=openai_api_key,
        transcribe_api_key=transcribe_api_key,
        transcribe_base_url=transcribe_base_url,
        transcribe_model=transcribe_model,
        target_language=target_language,
    )
    pipeline = SkeletonRipperPipeline()
    return pipeline.run(config, on_progress=on_progress)
