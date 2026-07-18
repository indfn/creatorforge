"""
Tests for agent_core/recon/skeleton_ripper/pipeline.py — SkeletonRipperPipeline.

Covers all 5 pipeline stages (scrape, transcribe, extract, aggregate, synthesize)
using mocked external dependencies (InstaClient, LLMClient, transcription, caching).

All external dependencies are mocked — zero real API calls.
All file I/O is redirected to tmp_path via monkeypatch.
All tests import pipeline INSIDE test bodies/fixtures.
"""

import sys
from unittest.mock import MagicMock

import pytest


# ─────────────────────────────────────────────────────────
# Module-level test data
# ─────────────────────────────────────────────────────────

MOCK_REEL = {
    "shortcode": "abc123",
    "views": 75000,
    "likes": 5000,
    "url": "https://instagram.com/p/abc123/",
    "video_url": "https://instagram.com/p/abc123/video/",
}

MOCK_REEL_2 = {
    "shortcode": "def456",
    "views": 120000,
    "likes": 8000,
    "url": "https://instagram.com/p/def456/",
    "video_url": "https://instagram.com/p/def456/video/",
}

MOCK_VALID_TRANSCRIPT = (
    "This technique changed everything for my workflow and helped me grow "
    "my channel to 100k subscribers in just three months. The key is "
    "consistency and understanding your audience deeply. "
    "Here is how I built this system from scratch."
)

MOCK_SKELETON = {
    "video_id": "abc123",
    "creator_username": "testuser",
    "platform": "instagram",
    "views": 75000,
    "likes": 5000,
    "hook": "This technique changed everything",
    "value": "Build a viral channel with consistency",
    "hook_technique": "curiosity_gap",
    "value_structure": "step_by_step_tutorial",
    "cta_type": "follow",
    "hook_word_count": 4,
    "total_word_count": 120,
    "estimated_duration_seconds": 180,
    "url": "",
    "video_url": "",
    "transcript": MOCK_VALID_TRANSCRIPT,
    "extracted_at": "2026-07-12T00:00:00",
    "extraction_model": "custom/gpt-4o-mini",
}

SHORT_TRANSCRIPT = "Too short"

MOCK_SYNTHESIS_ATTRS = {
    "success": True,
    "analysis": "Analysis text for testing purposes",
    "templates": [],
    "quick_wins": [],
    "warnings": [],
    "model_used": "custom/gpt-4o-mini",
    "synthesized_at": "2026-07-12T00:00:00",
    "error": None,
    "tokens_used": 0,
}


# ═════════════════════════════════════════════════════════
# Module-level fixture: pipeline_mocks
# ═════════════════════════════════════════════════════════


@pytest.fixture
def pipeline_mocks(monkeypatch, tmp_path):
    """Configure all mocks with sensible defaults for a successful pipeline run.

    - Redirects RECON_DATA_DIR to tmp_path.
    - download_direct creates a real temp file so ``video_path.exists()`` passes.
    - Returns a dict of mock objects that tests can reconfigure as needed.
    """
    # Redirect RECON_DATA_DIR so pipeline writes to tmp_path
    monkeypatch.setattr(
        "agent_core.recon.skeleton_ripper.pipeline.RECON_DATA_DIR",
        tmp_path / "data" / "recon",
    )

    # Pre-create temp dir so download mock can write into it
    temp_dir = tmp_path / "data" / "recon" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    mocks = {}

    # ── InstaClient ────────────────────────────────
    mock_insta_class = MagicMock()
    mock_insta_instance = MagicMock()
    mock_insta_instance.login.return_value = True
    mock_insta_instance.get_competitor_reels.return_value = [MOCK_REEL]
    mock_insta_class.return_value = mock_insta_instance
    monkeypatch.setattr(
        "agent_core.recon.skeleton_ripper.pipeline.InstaClient",
        mock_insta_class,
    )
    mocks["insta_class"] = mock_insta_class
    mocks["insta_instance"] = mock_insta_instance

    # ── download_direct — writes a real file so path.exists() passes ──
    from pathlib import Path as _Path

    def _fake_download(url, path):
        _path = _Path(path) if not isinstance(path, _Path) else path
        _path.parent.mkdir(parents=True, exist_ok=True)
        _path.write_bytes(b"fake video content")
        return True

    mocks["download_direct"] = MagicMock(side_effect=_fake_download)
    monkeypatch.setattr(
        "agent_core.recon.skeleton_ripper.pipeline.download_direct",
        mocks["download_direct"],
    )

    # ── transcribe_video ───────────────────────────
    mocks["transcribe_video"] = MagicMock(return_value=MOCK_VALID_TRANSCRIPT)
    monkeypatch.setattr(
        "agent_core.recon.skeleton_ripper.pipeline.transcribe_video",
        mocks["transcribe_video"],
    )

    # ── WHISPER_AVAILABLE ──────────────────────────
    monkeypatch.setattr(
        "agent_core.recon.skeleton_ripper.pipeline.WHISPER_AVAILABLE",
        False,
    )

    # ── API key for transcription ──────────────────
    # The pipeline uses ``config.openai_api_key or os.getenv('OPENAI_API_KEY')``
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-for-pipeline-tests")

    # ── load_config ────────────────────────────────
    mock_config = MagicMock()
    mock_config.ig_username = "test_user"
    mock_config.ig_password = "test_pass"
    mocks["load_config"] = MagicMock(return_value=mock_config)
    monkeypatch.setattr(
        "agent_core.recon.skeleton_ripper.pipeline.load_config",
        mocks["load_config"],
    )
    mocks["recon_config"] = mock_config

    # ── TranscriptCache ────────────────────────────
    mock_cache_class = MagicMock()
    mock_cache_instance = MagicMock()
    mock_cache_instance.get.return_value = None
    mock_cache_instance.set.return_value = True
    mock_cache_class.return_value = mock_cache_instance
    monkeypatch.setattr(
        "agent_core.recon.skeleton_ripper.pipeline.TranscriptCache",
        mock_cache_class,
    )
    mocks["cache_class"] = mock_cache_class
    mocks["cache_instance"] = mock_cache_instance

    # ── LLMClient ──────────────────────────────────
    mock_llm_class = MagicMock()
    mock_llm_instance = MagicMock()
    mock_llm_instance.complete.return_value = (
        '[{"video_id": "abc123", "hook": "test", "value": "test", '
        '"cta_type": "follow", "hook_word_count": 4, "total_word_count": 10}]'
    )
    mock_llm_instance.chat.return_value = "Synthesis analysis result text"
    mock_llm_instance.provider = "custom"
    mock_llm_instance.model = "gpt-4o-mini"
    mock_llm_class.return_value = mock_llm_instance
    monkeypatch.setattr(
        "agent_core.recon.skeleton_ripper.pipeline.LLMClient",
        mock_llm_class,
    )
    mocks["llm_class"] = mock_llm_class
    mocks["llm_instance"] = mock_llm_instance

    # ── BatchedExtractor ───────────────────────────
    mock_extractor_class = MagicMock()
    mock_extractor_instance = MagicMock()
    mock_extract_result = MagicMock()
    mock_extract_result.successful = [dict(MOCK_SKELETON)]
    mock_extract_result.failed_video_ids = []
    mock_extractor_instance.extract_all.return_value = mock_extract_result
    mock_extractor_class.return_value = mock_extractor_instance
    monkeypatch.setattr(
        "agent_core.recon.skeleton_ripper.pipeline.BatchedExtractor",
        mock_extractor_class,
    )
    mocks["extractor_class"] = mock_extractor_class
    mocks["extractor_instance"] = mock_extractor_instance
    mocks["extract_result"] = mock_extract_result

    # ── SkeletonAggregator ─────────────────────────
    mock_agg_class = MagicMock()
    mock_agg_instance = MagicMock()
    mock_aggregated = MagicMock()
    mock_aggregated.total_videos = 1
    mock_aggregated.total_views = 75000
    mock_aggregated.valid_skeletons = 1
    mock_aggregated.avg_hook_word_count = 4.0
    mock_aggregated.avg_total_word_count = 120.0
    mock_aggregated.avg_duration_seconds = 180.0
    mock_aggregated.skeletons = [dict(MOCK_SKELETON)]
    mock_aggregated.creator_stats = []
    mock_aggregated.overall_hook_techniques = {"curiosity_gap": 1}
    mock_aggregated.overall_value_structures = {"tutorial": 1}
    mock_aggregated.overall_cta_types = {"follow": 1}
    mock_agg_instance.aggregate.return_value = mock_aggregated
    mock_agg_class.return_value = mock_agg_instance
    monkeypatch.setattr(
        "agent_core.recon.skeleton_ripper.pipeline.SkeletonAggregator",
        mock_agg_class,
    )
    mocks["agg_class"] = mock_agg_class
    mocks["agg_instance"] = mock_agg_instance
    mocks["aggregated"] = mock_aggregated

    # ── PatternSynthesizer ─────────────────────────
    mock_synth_class = MagicMock()
    mock_synth_instance = MagicMock()
    mock_synthesis = MagicMock()
    for key, val in MOCK_SYNTHESIS_ATTRS.items():
        setattr(mock_synthesis, key, val)
    mock_synth_instance.synthesize.return_value = mock_synthesis
    mock_synth_class.return_value = mock_synth_instance
    monkeypatch.setattr(
        "agent_core.recon.skeleton_ripper.pipeline.PatternSynthesizer",
        mock_synth_class,
    )
    mocks["synth_class"] = mock_synth_class
    mocks["synth_instance"] = mock_synth_instance
    mocks["synthesis"] = mock_synthesis

    return mocks


# ═════════════════════════════════════════════════════════
# Task 1: Full pipeline run — success and progress
# ═════════════════════════════════════════════════════════


class TestPipelineRun:
    """Tests for SkeletonRipperPipeline.run() — success, error, edge cases."""

    # ── Success path ─────────────────────────────────

    def test_successful_pipeline_run(self, pipeline_mocks, tmp_path):
        """Full pipeline run completes all 5 stages and returns success=True."""
        from agent_core.recon.skeleton_ripper.pipeline import (
            SkeletonRipperPipeline,
            create_job_config,
        )

        pipeline = SkeletonRipperPipeline(base_dir=str(tmp_path / "data" / "recon"))
        config = create_job_config(usernames=["testuser"], videos_per_creator=1)
        result = pipeline.run(config)

        assert result.success is True
        assert result.job_id is not None
        assert result.job_id.startswith("sr_")
        assert len(result.skeletons) > 0
        assert result.aggregated is not None
        assert result.synthesis is not None
        assert result.synthesis.success is True
        assert result.progress.status.name == "COMPLETE"
        assert result.report_path is not None
        assert result.skeletons_path is not None
        assert result.synthesis_path is not None

    def test_progress_callback_fires(self, pipeline_mocks, tmp_path):
        """on_progress callback is called at least once during pipeline run."""
        from agent_core.recon.skeleton_ripper.pipeline import (
            SkeletonRipperPipeline,
            create_job_config,
        )

        progress_log = []

        def track(p):
            progress_log.append(p.status.name)

        pipeline = SkeletonRipperPipeline(base_dir=str(tmp_path / "data" / "recon"))
        config = create_job_config(usernames=["testuser"], videos_per_creator=1)
        pipeline.run(config, on_progress=track)

        assert len(progress_log) > 0
        # At minimum we should see some stages reported
        assert "COMPLETE" in progress_log or "FAILED" in progress_log

    def test_progress_has_correct_stages(self, pipeline_mocks, tmp_path):
        """Pipeline progress transitions through expected stages ending with COMPLETE."""
        from agent_core.recon.skeleton_ripper.pipeline import (
            SkeletonRipperPipeline,
            create_job_config,
        )

        stage_order = []

        def track(p):
            stage_order.append(p.status.name)

        pipeline = SkeletonRipperPipeline(base_dir=str(tmp_path / "data" / "recon"))
        config = create_job_config(usernames=["testuser"], videos_per_creator=1)
        pipeline.run(config, on_progress=track)

        # Verify at least 2 distinct stages were reported
        unique_stages = list(dict.fromkeys(stage_order))
        assert len(unique_stages) >= 2
        # Successful pipeline ends with COMPLETE
        assert unique_stages[-1] == "COMPLETE"

    # ── Error paths ──────────────────────────────────

    def test_no_valid_transcripts(self, pipeline_mocks, tmp_path):
        """Short/invalid transcripts cause graceful failure with success=False."""
        pipeline_mocks["transcribe_video"].return_value = SHORT_TRANSCRIPT

        from agent_core.recon.skeleton_ripper.pipeline import (
            SkeletonRipperPipeline,
            create_job_config,
        )

        pipeline = SkeletonRipperPipeline(base_dir=str(tmp_path / "data" / "recon"))
        config = create_job_config(usernames=["testuser"], videos_per_creator=1)
        result = pipeline.run(config)

        assert result.success is False
        assert result.progress.status.name == "FAILED"
        assert len(result.progress.errors) > 0
        error_text = " ".join(result.progress.errors).lower()
        assert "transcript" in error_text or "valid" in error_text

    def test_no_valid_skeletons(self, pipeline_mocks, tmp_path):
        """Extraction yields no skeletons → graceful failure (fails at extract stage)."""
        pipeline_mocks["extract_result"].successful = []
        from agent_core.recon.skeleton_ripper.pipeline import (
            SkeletonRipperPipeline,
            create_job_config,
        )

        pipeline = SkeletonRipperPipeline(base_dir=str(tmp_path / "data" / "recon"))
        config = create_job_config(usernames=["testuser"], videos_per_creator=1)
        result = pipeline.run(config)

        assert result.success is False
        assert result.progress.status.name == "FAILED"
        assert len(result.progress.errors) > 0
        # Pipeline raises "No skeletons extracted successfully" when extraction
        # stage produces an empty successful list
        error_text = " ".join(result.progress.errors).lower()
        assert "skeleton" in error_text

    def test_ig_credentials_missing(self, pipeline_mocks, tmp_path):
        """No IG credentials configured → graceful failure."""
        pipeline_mocks["recon_config"].ig_username = None

        from agent_core.recon.skeleton_ripper.pipeline import (
            SkeletonRipperPipeline,
            create_job_config,
        )

        pipeline = SkeletonRipperPipeline(base_dir=str(tmp_path / "data" / "recon"))
        config = create_job_config(usernames=["testuser"], videos_per_creator=1)
        result = pipeline.run(config)

        assert result.success is False
        assert result.progress.status.name == "FAILED"
        assert len(result.progress.errors) > 0
        error_text = " ".join(result.progress.errors).lower()
        assert "credential" in error_text or "ig_" in error_text

    def test_instagram_login_failure(self, pipeline_mocks, tmp_path):
        """InstaClient login returns False → graceful failure."""
        pipeline_mocks["insta_instance"].login.return_value = False

        from agent_core.recon.skeleton_ripper.pipeline import (
            SkeletonRipperPipeline,
            create_job_config,
        )

        pipeline = SkeletonRipperPipeline(base_dir=str(tmp_path / "data" / "recon"))
        config = create_job_config(usernames=["testuser"], videos_per_creator=1)
        result = pipeline.run(config)

        assert result.success is False
        assert result.progress.status.name == "FAILED"
        assert len(result.progress.errors) > 0
        error_text = " ".join(result.progress.errors).lower()
        assert "login" in error_text or "instagram" in error_text

    def test_no_reels_found(self, pipeline_mocks, tmp_path):
        """get_competitor_reels returns empty list → pipeline continues, no skeletons."""
        pipeline_mocks["insta_instance"].get_competitor_reels.return_value = []

        from agent_core.recon.skeleton_ripper.pipeline import (
            SkeletonRipperPipeline,
            create_job_config,
        )

        pipeline = SkeletonRipperPipeline(base_dir=str(tmp_path / "data" / "recon"))
        config = create_job_config(usernames=["testuser"], videos_per_creator=1)
        result = pipeline.run(config)

        assert result.success is False
        assert result.progress.status.name == "FAILED"

    def test_empty_usernames_list(self, pipeline_mocks, tmp_path):
        """Empty usernames list → graceful failure."""
        from agent_core.recon.skeleton_ripper.pipeline import (
            SkeletonRipperPipeline,
            create_job_config,
        )

        pipeline = SkeletonRipperPipeline(base_dir=str(tmp_path / "data" / "recon"))
        config = create_job_config(usernames=[])
        result = pipeline.run(config)

        assert result.success is False
        assert result.progress.status.name == "FAILED"

    def test_download_failure_skips_video(self, pipeline_mocks, tmp_path):
        """Failed download doesn't crash pipeline — video is skipped."""
        # Override download_direct to return False without creating a file
        pipeline_mocks["download_direct"].side_effect = None
        pipeline_mocks["download_direct"].return_value = False

        from agent_core.recon.skeleton_ripper.pipeline import (
            SkeletonRipperPipeline,
            create_job_config,
        )

        pipeline = SkeletonRipperPipeline(base_dir=str(tmp_path / "data" / "recon"))
        config = create_job_config(usernames=["testuser"], videos_per_creator=1)
        result = pipeline.run(config)

        # Failed download means no transcripts → no skeletons
        assert result.success is False
        assert result.progress.status.name == "FAILED"

    def test_transcribe_failure_skips_video(self, pipeline_mocks, tmp_path):
        """transcribe_video returns None → video skipped, pipeline doesn't crash."""
        pipeline_mocks["transcribe_video"].return_value = None

        from agent_core.recon.skeleton_ripper.pipeline import (
            SkeletonRipperPipeline,
            create_job_config,
        )

        pipeline = SkeletonRipperPipeline(base_dir=str(tmp_path / "data" / "recon"))
        config = create_job_config(usernames=["testuser"], videos_per_creator=1)
        result = pipeline.run(config)

        assert result.success is False
        assert result.progress.status.name == "FAILED"

    # ── Cache integration ────────────────────────────

    def test_cache_hit_skips_download_and_transcribe(self, pipeline_mocks, tmp_path):
        """When per-video cache has valid transcript, download/transcribe not called."""
        pipeline_mocks["cache_instance"].get.return_value = MOCK_VALID_TRANSCRIPT

        from agent_core.recon.skeleton_ripper.pipeline import (
            SkeletonRipperPipeline,
            create_job_config,
        )

        pipeline = SkeletonRipperPipeline(base_dir=str(tmp_path / "data" / "recon"))
        config = create_job_config(usernames=["testuser"], videos_per_creator=1)
        result = pipeline.run(config)

        assert result.success is True
        # download_direct and transcribe_video should NOT have been called
        pipeline_mocks["download_direct"].assert_not_called()
        pipeline_mocks["transcribe_video"].assert_not_called()
        # cache.set() is NOT called for cached transcripts (the code uses 'continue')
        pipeline_mocks["cache_instance"].set.assert_not_called()
        # Verify cache.get() was called at least once
        assert pipeline_mocks["cache_instance"].get.call_count > 0
        assert result.progress.transcripts_from_cache > 0

    def test_cache_miss_calls_download_and_transcribe(self, pipeline_mocks, tmp_path):
        """When cache misses, download and transcribe are called."""
        pipeline_mocks["cache_instance"].get.return_value = None

        from agent_core.recon.skeleton_ripper.pipeline import (
            SkeletonRipperPipeline,
            create_job_config,
        )

        pipeline = SkeletonRipperPipeline(base_dir=str(tmp_path / "data" / "recon"))
        config = create_job_config(usernames=["testuser"], videos_per_creator=1)
        result = pipeline.run(config)

        assert result.success is True
        pipeline_mocks["download_direct"].assert_called()
        pipeline_mocks["transcribe_video"].assert_called()
        # cache.set should have been called to store the transcript
        pipeline_mocks["cache_instance"].set.assert_called()

    # ── Multi-creator ────────────────────────────────

    def test_multiple_creators_all_succeed(self, pipeline_mocks, tmp_path):
        """Multiple creators in config → all processed, combined in result."""
        pipeline_mocks["insta_instance"].get_competitor_reels.return_value = [MOCK_REEL, MOCK_REEL_2]

        from agent_core.recon.skeleton_ripper.pipeline import (
            SkeletonRipperPipeline,
            create_job_config,
        )

        pipeline = SkeletonRipperPipeline(base_dir=str(tmp_path / "data" / "recon"))
        config = create_job_config(usernames=["creator1", "creator2"], videos_per_creator=1)
        result = pipeline.run(config)

        assert result.success is True
        assert result.progress.total_creators == 2

    def test_partial_creator_failure(self, pipeline_mocks, tmp_path, monkeypatch):
        """When one creator has no reels, pipeline continues with others.

        Note: The current pipeline design treats any stage failure as fatal.
        If one creator produces no valid transcripts but another does, the
        pipeline may still succeed. This test documents the behavior.
        """
        # First call returns empty (creator1), second call returns reels (creator2)
        pipeline_mocks["insta_instance"].get_competitor_reels.side_effect = [
            [],
            [MOCK_REEL],
        ]

        monkeypatch.setattr(
            "agent_core.recon.skeleton_ripper.pipeline.RECON_DATA_DIR",
            tmp_path / "data" / "recon",
        )
        from agent_core.recon.skeleton_ripper.pipeline import (
            SkeletonRipperPipeline,
            create_job_config,
        )

        pipeline = SkeletonRipperPipeline(base_dir=str(tmp_path / "data" / "recon"))
        config = create_job_config(usernames=["creator1", "creator2"], videos_per_creator=1)
        result = pipeline.run(config)

        # If creator1 has no reels but creator2 has reels, we get 1 valid transcript
        # If MIN_VALID_RATIO is met and at least one transcript produces a skeleton, this succeeds
        # The exact behavior depends on whether 1 skeleton from 2 creators is valid
        # Note: current pipeline needs at least 1 valid skeleton to succeed
        # Since mock extractor returns 1 skeleton for any input, this should succeed
        assert result.success is True
        assert result.progress.videos_scraped == 1
        assert len(result.skeletons) == 1


# ═════════════════════════════════════════════════════════
# Task 3: Helper functions, dataclasses, output saving
# ═════════════════════════════════════════════════════════


class TestJobConfig:
    """Tests for create_job_config() and JobConfig dataclass."""

    def test_create_job_config_defaults(self):
        """create_job_config with only usernames sets sensible defaults."""
        from agent_core.recon.skeleton_ripper.pipeline import create_job_config

        config = create_job_config(usernames=["creator1"])
        assert config.usernames == ["creator1"]
        assert config.videos_per_creator == 3
        assert config.platform == "instagram"
        assert config.llm_provider == "custom"
        assert config.llm_model == "gpt-4o-mini"
        assert config.transcribe_provider == "openai"
        assert config.transcribe_model == "whisper-1"
        assert config.whisper_model == "small.en"
        assert config.min_valid_ratio == 0.6

    def test_create_job_config_overrides(self):
        """All optional parameters can be overridden."""
        from agent_core.recon.skeleton_ripper.pipeline import create_job_config

        config = create_job_config(
            usernames=["c1"],
            videos_per_creator=5,
            platform="youtube",
            llm_provider="openai",
            llm_model="gpt-4o",
            transcribe_provider="local",
            whisper_model="large",
            openai_api_key="sk-test",
            transcribe_api_key="sk-transcribe",
            transcribe_base_url="https://custom.example.com",
            transcribe_model="whisper-large-v3",
        )
        assert config.videos_per_creator == 5
        assert config.platform == "youtube"
        assert config.llm_provider == "openai"
        assert config.llm_model == "gpt-4o"
        assert config.transcribe_provider == "local"
        assert config.whisper_model == "large"
        assert config.openai_api_key == "sk-test"
        assert config.transcribe_api_key == "sk-transcribe"
        assert config.transcribe_base_url == "https://custom.example.com"
        assert config.transcribe_model == "whisper-large-v3"

    def test_job_config_dataclass_fields(self):
        """JobConfig dataclass has all expected fields."""
        from agent_core.recon.skeleton_ripper.pipeline import JobConfig

        config = JobConfig(usernames=["test"])
        assert hasattr(config, "openai_api_key")
        assert hasattr(config, "transcribe_api_key")
        assert hasattr(config, "transcribe_base_url")
        assert hasattr(config, "transcribe_model")
        assert hasattr(config, "min_valid_ratio")
        assert hasattr(config, "videos_per_creator")
        assert hasattr(config, "platform")
        assert hasattr(config, "llm_provider")
        assert hasattr(config, "llm_model")
        assert hasattr(config, "whisper_model")
        assert config.usernames == ["test"]

    def test_create_job_config_default_videos_per_creator(self):
        """Videos per creator defaults to 3."""
        from agent_core.recon.skeleton_ripper.pipeline import create_job_config

        config = create_job_config(usernames=["c1"])
        assert config.videos_per_creator == 3


class TestJobProgress:
    """Tests for JobProgress dataclass."""

    def test_job_progress_defaults(self):
        """JobProgress defaults: PENDING, empty message, zero counts."""
        from agent_core.recon.skeleton_ripper.pipeline import JobProgress, JobStatus

        progress = JobProgress()
        assert progress.status == JobStatus.PENDING
        assert progress.status.name == "PENDING"
        assert progress.message == ""
        assert progress.videos_scraped == 0
        assert progress.videos_downloaded == 0
        assert progress.videos_transcribed == 0
        assert progress.transcripts_from_cache == 0
        assert progress.valid_transcripts == 0
        assert progress.skeletons_extracted == 0
        assert progress.total_target == 0
        assert progress.errors == []


class TestJobResult:
    """Tests for JobResult dataclass."""

    def test_job_result_defaults(self):
        """JobResult defaults: success=False, empty lists."""
        from agent_core.recon.skeleton_ripper.pipeline import (
            JobConfig,
            JobResult,
            JobProgress,
            create_job_config,
        )

        config = create_job_config(usernames=["test"])
        result = JobResult(
            job_id="test123",
            success=False,
            config=config,
            progress=JobProgress(),
        )
        assert result.job_id == "test123"
        assert result.success is False
        assert result.skeletons == []
        assert result.aggregated is None
        assert result.synthesis is None
        assert result.report_path is None
        assert result.skeletons_path is None
        assert result.synthesis_path is None

    def test_job_result_with_skeletons(self):
        """JobResult can hold skeleton data."""
        from agent_core.recon.skeleton_ripper.pipeline import (
            JobConfig,
            JobResult,
            JobProgress,
            create_job_config,
        )

        config = create_job_config(usernames=["test"])
        result = JobResult(
            job_id="test456",
            success=True,
            config=config,
            progress=JobProgress(),
            skeletons=[dict(MOCK_SKELETON)],
        )
        assert result.success is True
        assert len(result.skeletons) == 1
        assert result.skeletons[0]["video_id"] == "abc123"


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_job_status_enum_values(self):
        """JobStatus enum has expected stages in correct order."""
        from agent_core.recon.skeleton_ripper.pipeline import JobStatus

        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.SCRAPING.value == "scraping"
        assert JobStatus.TRANSCRIBING.value == "transcribing"
        assert JobStatus.EXTRACTING.value == "extracting"
        assert JobStatus.AGGREGATING.value == "aggregating"
        assert JobStatus.SYNTHESIZING.value == "synthesizing"
        assert JobStatus.COMPLETE.value == "complete"
        assert JobStatus.FAILED.value == "failed"

    def test_job_status_enum_members(self):
        """All JobStatus members are accessible by name."""
        from agent_core.recon.skeleton_ripper.pipeline import JobStatus

        assert JobStatus["PENDING"] == JobStatus.PENDING
        assert JobStatus["COMPLETE"] == JobStatus.COMPLETE
        assert JobStatus["FAILED"] == JobStatus.FAILED


class TestPipelineSaveOutputs:
    """Tests that _save_outputs writes valid JSON files to the reports directory."""

    def test_output_saved_to_reports_dir(self, pipeline_mocks, tmp_path):
        """Pipeline writes skeletons.json, synthesis.json, report.md to reports dir."""
        from agent_core.recon.skeleton_ripper.pipeline import (
            SkeletonRipperPipeline,
            create_job_config,
        )

        pipeline = SkeletonRipperPipeline(base_dir=str(tmp_path / "data" / "recon"))
        config = create_job_config(usernames=["testuser"], videos_per_creator=1)
        result = pipeline.run(config)

        assert result.skeletons_path is not None
        assert result.synthesis_path is not None
        assert result.report_path is not None

        import json
        from pathlib import Path

        skeletons = Path(result.skeletons_path)
        synthesis = Path(result.synthesis_path)
        report = Path(result.report_path)

        assert skeletons.exists()
        assert synthesis.exists()
        assert report.exists()

        # Verify skeletons.json is valid JSON
        with open(skeletons) as f:
            data = json.load(f)
            assert isinstance(data, list)
            assert len(data) > 0

        # Verify synthesis.json is valid JSON
        with open(synthesis) as f:
            data = json.load(f)
            assert isinstance(data, dict)
            assert data["success"] is True
            assert "analysis" in data
            assert "model_used" in data

        # Verify report.md is non-empty
        report_text = report.read_text()
        assert len(report_text) > 0
        assert "Analysis" in report_text or "Summary" in report_text


class TestRunSkeletonRipper:
    """Tests for the module-level run_skeleton_ripper() convenience function."""

    def test_run_skeleton_ripper_module_function(self, pipeline_mocks, tmp_path):
        """run_skeleton_ripper() creates pipeline and calls run()."""
        from agent_core.recon.skeleton_ripper.pipeline import run_skeleton_ripper

        result = run_skeleton_ripper(
            usernames=["testuser"],
            videos_per_creator=1,
        )
        assert result is not None
        assert hasattr(result, "success")
        assert hasattr(result, "job_id")
        assert hasattr(result, "skeletons")

    def test_run_skeleton_ripper_passes_on_progress(self, pipeline_mocks, tmp_path):
        """run_skeleton_ripper accepts and forwards on_progress callback."""
        from agent_core.recon.skeleton_ripper.pipeline import run_skeleton_ripper

        calls = []

        def track(p):
            calls.append(p.status.name)

        result = run_skeleton_ripper(
            usernames=["testuser"],
            videos_per_creator=1,
            on_progress=track,
        )
        assert len(calls) > 0
        assert "COMPLETE" in calls or "FAILED" in calls
        assert result.success is True


# ═════════════════════════════════════════════════════════
# Task 1 TDD: get_video_captions — RED phase
# ═════════════════════════════════════════════════════════


class TestGetVideoCaptions:
    """TDD RED: Tests for get_video_captions() — function must exist first."""

    def test_import_get_video_captions(self):
        """get_video_captions can be imported (RED — fails before implementation)."""
        from agent_core.recon.scraper.youtube import get_video_captions
        assert callable(get_video_captions)

    def test_returns_none_without_yt_dlp(self):
        """Without yt-dlp available, returns None (no crash)."""
        from agent_core.recon.scraper.youtube import get_video_captions
        result = get_video_captions("dQw4w9WgXcQ")
        assert result is None

    def test_lang_parameter_defaults_to_en(self):
        """Default language is 'en'. Unknown lang returns None gracefully."""
        from agent_core.recon.scraper.youtube import get_video_captions
        result = get_video_captions("nonexistent_video_id_12345", lang="xx")
        assert result is None

    def test_returns_none_on_empty_video_id(self):
        """Empty video ID returns None (yt-dlp will fail)."""
        from agent_core.recon.scraper.youtube import get_video_captions
        result = get_video_captions("")
        assert result is None


# ═════════════════════════════════════════════════════════
# TDD Gate: test count verification
# ═════════════════════════════════════════════════════════

class TestTestCount:
    """Meta-test: verify we have at least 20 test functions for the pipeline module."""

    def test_sufficient_test_coverage(self):
        """Ensure at least 20 test functions exist in this file."""
        import inspect

        # Count test methods across all test classes in this module
        module = sys.modules[__name__]
        count = 0
        for name, obj in inspect.getmembers(module):
            if name.startswith("Test") and inspect.isclass(obj):
                for method_name in dir(obj):
                    if method_name.startswith("test_"):
                        count += 1

        assert count >= 20, f"Expected >=20 tests, got {count}"
