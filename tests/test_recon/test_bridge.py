"""
Tests for agent_core/recon/bridge.py — skeleton-to-topic conversion,
pillar matching, topic title generation, JSONL saving, and skeleton loading.

All file I/O is isolated via monkeypatch + tmp_path. The engine scoring
function is mocked to avoid coupling to scoring engine internals.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_core.recon import bridge


# ─────────────────────────────────────────────────────────
# Module-level test data
# ─────────────────────────────────────────────────────────

SAMPLE_SKELETON = {
    "creator_username": "testcreator",
    "platform": "instagram",
    "views": 75000,
    "likes": 5000,
    "hook": "This technique changed everything for my workflow",
    "value": "In this video I show you how to build a viral channel step by step with automation",
    "hook_technique": "curiosity_gap",
    "value_structure": "step_by_step_tutorial",
    "url": "https://instagram.com/p/abc123/",
    "video_url": "https://instagram.com/p/abc123/video/",
    "transcript": "This technique changed everything for my workflow. In this video I show you how to build a viral channel step by step with automation.",
    "extracted_at": "2026-07-12T00:00:00",
    "extraction_model": "custom/gpt-4o-mini",
}

SAMPLE_SKELETON_LOW_VIEWS = {
    "creator_username": "smallcreator",
    "platform": "youtube",
    "views": 3200,
    "likes": 150,
    "hook": "Quick tip for better results",
    "value": "Try this simple workflow change",
    "hook_technique": "direct_benefit",
    "value_structure": "quick_tip",
    "url": "https://youtube.com/watch?v=xyz456/",
    "video_url": "https://youtube.com/watch?v=xyz456/",
    "transcript": "Quick tip for better results. Try this simple workflow change.",
    "extracted_at": "2026-07-12T00:00:00",
    "extraction_model": "custom/gpt-4o-mini",
}

MOCK_SCORING = {
    "icp_relevance": 7,
    "timeliness": 6,
    "content_gap": 8,
    "proof_potential": 7,
    "total": 28,
    "weighted_total": 28.0,
}


# ─────────────────────────────────────────────────────────
# Helper fixture for setting up a brain file
# ─────────────────────────────────────────────────────────


@pytest.fixture
def brain_with_pillars(tmp_path, monkeypatch):
    """Set up a temporary brain file with known pillars, weights, and competitors.

    Returns: List[str] of pillar names for use in assertions.
    """
    brain_file = tmp_path / "agent-brain.json"
    brain_file.write_text(json.dumps({
        "pillars": [
            {"name": "AI Automation", "keywords": ["automation", "AI", "workflow"]},
            {"name": "Growth Hacking", "keywords": ["growth", "viral", "traffic"]},
        ],
        "learning_weights": {
            "icp_relevance": 1.0,
            "timeliness": 1.0,
            "content_gap": 1.0,
            "proof_potential": 1.0,
        },
        "competitors": [],
        "icp": {
            "pain_points": ["scaling revenue", "automating workflows"],
            "goals": ["grow revenue", "automate operations"],
            "segments": ["founders", "startups"],
        },
    }))
    monkeypatch.setattr(bridge, "BRAIN_FILE", brain_file)
    return ["AI Automation", "Growth Hacking"]


@pytest.fixture
def mock_engine_score(monkeypatch):
    """Mock bridge.engine_score_topic to return a fixed scoring dict."""
    monkeypatch.setattr(bridge, "engine_score_topic",
                        lambda **kwargs: dict(MOCK_SCORING))


# ═════════════════════════════════════════════════════════
# Task 1: Helper function tests
# ═════════════════════════════════════════════════════════


class TestLoadBrainPillars:
    """Tests for bridge.load_brain_pillars()."""

    def test_missing_brain_file_returns_empty(self, monkeypatch, tmp_path):
        """BRAIN_FILE doesn't exist => []."""
        monkeypatch.setattr(bridge, "BRAIN_FILE", tmp_path / "nonexistent.json")
        assert bridge.load_brain_pillars() == []

    def test_returns_pillar_names(self, monkeypatch, tmp_path):
        """Returns [name for each pillar in brain['pillars']]."""
        brain_file = tmp_path / "agent-brain.json"
        brain_file.write_text(json.dumps({
            "pillars": [
                {"name": "AI Automation", "keywords": ["AI"]},
                {"name": "Growth Hacking", "keywords": ["growth"]},
            ]
        }))
        monkeypatch.setattr(bridge, "BRAIN_FILE", brain_file)
        result = bridge.load_brain_pillars()
        assert result == ["AI Automation", "Growth Hacking"]

    def test_handles_pillars_without_name(self, monkeypatch, tmp_path):
        """Pillars missing 'name' key return empty string entries."""
        brain_file = tmp_path / "agent-brain.json"
        brain_file.write_text(json.dumps({
            "pillars": [
                {"name": "AI Automation", "keywords": ["AI"]},
                {"keywords": ["growth"]},        # no 'name' key
                {"name": "Growth Hacking", "keywords": ["growth"]},
            ]
        }))
        monkeypatch.setattr(bridge, "BRAIN_FILE", brain_file)
        # Code does [p.get("name", "") for p in ...] so "" for missing names
        result = bridge.load_brain_pillars()
        assert result == ["AI Automation", "", "Growth Hacking"]

    def test_handles_empty_pillars_list(self, monkeypatch, tmp_path):
        """Empty pillars list returns []."""
        brain_file = tmp_path / "agent-brain.json"
        brain_file.write_text(json.dumps({
            "pillars": []
        }))
        monkeypatch.setattr(bridge, "BRAIN_FILE", brain_file)
        assert bridge.load_brain_pillars() == []

    def test_missing_pillars_key_returns_empty(self, monkeypatch, tmp_path):
        """Brain without 'pillars' key returns []."""
        brain_file = tmp_path / "agent-brain.json"
        brain_file.write_text(json.dumps({"competitors": []}))
        monkeypatch.setattr(bridge, "BRAIN_FILE", brain_file)
        assert bridge.load_brain_pillars() == []


class TestLoadBrainLearningWeights:
    """Tests for bridge.load_brain_learning_weights()."""

    def test_missing_file_returns_default_weights(self, monkeypatch, tmp_path):
        """Missing brain file => default weights (all 1.0)."""
        monkeypatch.setattr(bridge, "BRAIN_FILE", tmp_path / "nonexistent.json")
        expected = {
            "icp_relevance": 1.0,
            "timeliness": 1.0,
            "content_gap": 1.0,
            "proof_potential": 1.0,
        }
        assert bridge.load_brain_learning_weights() == expected

    def test_returns_weights_from_brain(self, monkeypatch, tmp_path):
        """Brain file weights are returned as-is."""
        brain_file = tmp_path / "agent-brain.json"
        brain_file.write_text(json.dumps({
            "learning_weights": {
                "icp_relevance": 2.0,
                "timeliness": 1.5,
                "content_gap": 0.5,
                "proof_potential": 1.0,
            }
        }))
        monkeypatch.setattr(bridge, "BRAIN_FILE", brain_file)
        result = bridge.load_brain_learning_weights()
        assert result["icp_relevance"] == 2.0
        assert result["timeliness"] == 1.5
        assert result["content_gap"] == 0.5
        assert result["proof_potential"] == 1.0

    def test_handles_partial_weights(self, monkeypatch, tmp_path):
        """Brain with partial weights returns only those keys."""
        brain_file = tmp_path / "agent-brain.json"
        brain_file.write_text(json.dumps({
            "learning_weights": {
                "icp_relevance": 2.0,
                "timeliness": 1.5,
            }
        }))
        monkeypatch.setattr(bridge, "BRAIN_FILE", brain_file)
        result = bridge.load_brain_learning_weights()
        assert result["icp_relevance"] == 2.0
        assert result["timeliness"] == 1.5
        # The code returns the dict as-is — missing keys are NOT auto-filled
        assert "content_gap" not in result
        assert "proof_potential" not in result


class TestGenerateTopicTitle:
    """Tests for the private _generate_topic_title()."""

    def test_uses_value_as_primary_source(self):
        """Longer value string => first sentence of value used as title."""
        title = bridge._generate_topic_title(
            hook="Short hook",
            value="Build a viral channel with automation step by step. Then we deploy it.",
            creator="testcreator",
        )
        assert title == "Build a viral channel with automation step by step"

    def test_falls_back_to_hook_when_value_short(self):
        """value < 10 chars => uses hook."""
        title = bridge._generate_topic_title(
            hook="This technique changed everything",
            value="Short",
            creator="testcreator",
        )
        assert "This technique changed everything" in title

    def test_falls_back_to_hook_when_value_empty(self):
        """Empty value string => uses hook."""
        title = bridge._generate_topic_title(
            hook="This technique changed everything",
            value="",
            creator="testcreator",
        )
        assert "This technique changed everything" in title

    def test_falls_back_to_creator_name(self):
        """Both hook and value short => 'Content pattern from @{creator}'."""
        title = bridge._generate_topic_title(
            hook="Hi",
            value="OK",
            creator="testcreator",
        )
        assert title == "Content pattern from @testcreator"

    def test_truncates_long_title(self):
        """Title > 80 chars => truncated to 77 + '...'."""
        long_value = "A" * 100
        title = bridge._generate_topic_title(
            hook="hook",
            value=long_value,
            creator="testcreator",
        )
        assert len(title) <= 80
        assert title.endswith("...")

    def test_value_empty_and_hook_empty_uses_creator(self):
        """Both value and hook empty => 'Content pattern from @{creator}'."""
        title = bridge._generate_topic_title(
            hook="",
            value="",
            creator="nobody",
        )
        assert title == "Content pattern from @nobody"


class TestMatchPillars:
    """Tests for the private _match_pillars()."""

    def test_direct_match(self):
        """Pillar name appears in text => matched."""
        result = bridge._match_pillars(
            "Learn about AI Automation techniques",
            ["AI Automation", "Growth Hacking"],
        )
        assert "AI Automation" in result
        assert "Growth Hacking" not in result

    def test_no_match_returns_first_pillar(self):
        """No pillar name in text => includes first pillar as catch-all."""
        result = bridge._match_pillars(
            "Cooking recipes and food",
            ["AI Automation", "Growth Hacking"],
        )
        assert result == ["AI Automation"]

    def test_empty_pillars_returns_empty(self):
        """No pillars => []."""
        result = bridge._match_pillars(
            "Some text about AI",
            [],
        )
        assert result == []

    def test_multiple_matches(self):
        """Multiple pillar names in text => all matched."""
        result = bridge._match_pillars(
            "AI Automation and Growth Hacking techniques for viral growth",
            ["AI Automation", "Growth Hacking", "Brand Building"],
        )
        assert "AI Automation" in result
        assert "Growth Hacking" in result
        assert "Brand Building" not in result

    def test_empty_text_returns_first_pillar(self):
        """Empty text => catch-all first pillar."""
        result = bridge._match_pillars(
            "",
            ["AI Automation", "Growth Hacking"],
        )
        assert result == ["AI Automation"]

    def test_case_insensitive_matching(self):
        """Pillar matching is case-insensitive."""
        result = bridge._match_pillars(
            "ai automation tools",
            ["AI Automation"],
        )
        assert "AI Automation" in result

    def test_text_with_no_relevant_keywords_gets_catch_all(self):
        """No keyword overlap => catch-all pillar."""
        result = bridge._match_pillars(
            "Cooking, recipes, food, kitchen",
            ["AI Automation", "Growth Hacking"],
        )
        assert result == ["AI Automation"]


# ═════════════════════════════════════════════════════════
# Task 2: skeleton_to_topic and generate_topics_from_skeletons
# ═════════════════════════════════════════════════════════


class TestSkeletonToTopic:
    """Tests for bridge.skeleton_to_topic() — full conversion."""

    @pytest.fixture
    def setup(self, mock_engine_score, brain_with_pillars):
        """Set up mocked engine and brain pillars."""
        return brain_with_pillars

    def test_returns_topic_with_all_required_keys(self, setup):
        """Topic dict has all expected keys."""
        topic = bridge.skeleton_to_topic(SAMPLE_SKELETON, 1, "20260712", setup)
        expected_keys = {
            "id", "title", "description", "source", "discovered_at",
            "scoring", "pillars", "competitor_coverage", "status", "notes",
        }
        assert expected_keys.issubset(topic.keys())

    def test_topic_id_format(self, setup):
        """id = 'topic_{date_str}_{index:03d}'."""
        topic = bridge.skeleton_to_topic(SAMPLE_SKELETON, 42, "20260712", setup)
        assert topic["id"] == "topic_20260712_042"

    def test_scoring_contains_six_keys(self, setup):
        """scoring dict has all 6 expected keys."""
        topic = bridge.skeleton_to_topic(SAMPLE_SKELETON, 1, "20260712", setup)
        scoring = topic["scoring"]
        expected_keys = {
            "icp_relevance", "timeliness", "content_gap",
            "proof_potential", "total", "weighted_total",
        }
        assert expected_keys.issubset(scoring.keys())

    def test_is_competitor_flag_set(self, setup, monkeypatch):
        """Verifies engine_score_topic is called with is_competitor=True."""
        call_kwargs = {}

        def capture_call(**kwargs):
            call_kwargs.update(kwargs)
            return dict(MOCK_SCORING)

        monkeypatch.setattr(bridge, "engine_score_topic", capture_call)
        bridge.skeleton_to_topic(SAMPLE_SKELETON, 1, "20260712", setup)
        assert call_kwargs.get("is_competitor") is True

    def test_pillars_matched_from_pillar_list(self, setup):
        """Pillars list in topic matches pillars parameter."""
        topic = bridge.skeleton_to_topic(SAMPLE_SKELETON, 1, "20260712", setup)
        assert isinstance(topic["pillars"], list)

    def test_competitor_coverage_lists_creator(self, setup):
        """competitor_coverage has entry with @creator, url, performance."""
        topic = bridge.skeleton_to_topic(SAMPLE_SKELETON, 1, "20260712", setup)
        coverage = topic["competitor_coverage"]
        assert len(coverage) == 1
        entry = coverage[0]
        assert entry["competitor"] == "@testcreator"
        assert entry["url"] == SAMPLE_SKELETON["url"]
        assert "views" in entry["performance"]

    def test_source_author_prefixed_with_at(self, setup):
        """source.author starts with '@'."""
        topic = bridge.skeleton_to_topic(SAMPLE_SKELETON, 1, "20260712", setup)
        assert topic["source"]["author"].startswith("@")

    def test_source_has_correct_platform(self, setup):
        """source.platform is 'competitor_analysis'."""
        topic = bridge.skeleton_to_topic(SAMPLE_SKELETON, 1, "20260712", setup)
        assert topic["source"]["platform"] == "competitor_analysis"

    def test_notes_contain_hook_technique_and_value_structure(self, setup):
        """notes string includes hook_technique and value_structure."""
        topic = bridge.skeleton_to_topic(SAMPLE_SKELETON, 1, "20260712", setup)
        assert "curiosity_gap" in topic["notes"]
        assert "step_by_step_tutorial" in topic["notes"]

    def test_missing_creator_defaults_to_unknown(self, setup):
        """Skeleton without creator_username => 'unknown' in source."""
        skeleton = dict(SAMPLE_SKELETON)
        del skeleton["creator_username"]
        topic = bridge.skeleton_to_topic(skeleton, 1, "20260712", setup)
        assert topic["source"]["author"] == "@unknown"
        assert topic["competitor_coverage"][0]["competitor"] == "@unknown"

    def test_description_contains_views_formatted_with_commas(self, setup):
        """Description includes views formatted with commas (e.g., '75,000')."""
        topic = bridge.skeleton_to_topic(SAMPLE_SKELETON, 1, "20260712", setup)
        assert "75,000" in topic["description"]

    def test_status_is_new(self, setup):
        """status field defaults to 'new'."""
        topic = bridge.skeleton_to_topic(SAMPLE_SKELETON, 1, "20260712", setup)
        assert topic["status"] == "new"

    def test_source_url_matches_skeleton(self, setup):
        """source.url comes from skeleton's url field."""
        topic = bridge.skeleton_to_topic(SAMPLE_SKELETON, 1, "20260712", setup)
        assert topic["source"]["url"] == SAMPLE_SKELETON["url"]

    def test_engagement_signals_in_source(self, setup):
        """source.engagement_signals contains formatted views."""
        topic = bridge.skeleton_to_topic(SAMPLE_SKELETON, 1, "20260712", setup)
        assert "75,000 views on instagram" in topic["source"]["engagement_signals"]

    def test_low_views_still_formatted_correctly(self, setup):
        """Low view counts are formatted with commas."""
        topic = bridge.skeleton_to_topic(SAMPLE_SKELETON_LOW_VIEWS, 1, "20260712", setup)
        assert "3,200" in topic["description"]
        assert "3,200 views on youtube" in topic["source"]["engagement_signals"]


class TestGenerateTopicsFromSkeletons:
    """Tests for bridge.generate_topics_from_skeletons()."""

    def test_generates_correct_number_of_topics(self, mock_engine_score, brain_with_pillars):
        """len(skeletons) == len(topics)."""
        skeletons = [SAMPLE_SKELETON, SAMPLE_SKELETON_LOW_VIEWS]
        topics = bridge.generate_topics_from_skeletons(skeletons, start_index=1)
        assert len(topics) == 2

    def test_topic_ids_increment_from_start_index(self, mock_engine_score, brain_with_pillars):
        """start_index=5 => first topic id ends with '005'."""
        skeletons = [SAMPLE_SKELETON]
        topics = bridge.generate_topics_from_skeletons(skeletons, start_index=5)
        # ID format: topic_{date_str}_{index:03d}
        assert topics[0]["id"].endswith("005")

    def test_empty_skeletons_returns_empty(self, mock_engine_score, brain_with_pillars):
        """[] => []."""
        topics = bridge.generate_topics_from_skeletons([], start_index=1)
        assert topics == []

    def test_each_topic_has_unique_id(self, mock_engine_score, brain_with_pillars):
        """All topic IDs are unique."""
        skeletons = [SAMPLE_SKELETON, SAMPLE_SKELETON_LOW_VIEWS,
                     dict(SAMPLE_SKELETON, creator_username="creator3"),
                     dict(SAMPLE_SKELETON, creator_username="creator4")]
        topics = bridge.generate_topics_from_skeletons(skeletons, start_index=3)
        ids = [t["id"] for t in topics]
        assert len(ids) == len(set(ids))

    def test_single_skeleton_generates_one_topic(self, mock_engine_score, brain_with_pillars):
        """Single skeleton input => one topic output."""
        topics = bridge.generate_topics_from_skeletons([SAMPLE_SKELETON], start_index=1)
        assert len(topics) == 1

    def test_pillars_loaded_from_brain(self, mock_engine_score, brain_with_pillars):
        """Pillars in topics come from brain file."""
        topics = bridge.generate_topics_from_skeletons([SAMPLE_SKELETON], start_index=1)
        assert len(topics[0]["pillars"]) > 0


# ═════════════════════════════════════════════════════════
# Task 3: save_topics_jsonl and load_latest_skeletons
# ═════════════════════════════════════════════════════════


class TestSaveTopicsJsonl:
    """Tests for bridge.save_topics_jsonl()."""

    @pytest.fixture
    def topic(self):
        """Minimal topic dict for JSONL tests."""
        return {
            "id": "topic_20260712_001",
            "title": "Test Topic",
            "description": "A topic for testing",
            "source": {"platform": "competitor_analysis", "url": "", "author": "@test", "engagement_signals": ""},
            "discovered_at": "2026-07-12T00:00:00Z",
            "scoring": {},
            "pillars": ["AI Automation"],
            "competitor_coverage": [],
            "status": "new",
            "notes": "test",
        }

    def test_saves_to_correct_path(self, monkeypatch, tmp_path, topic):
        """File saved at TOPICS_DIR/{date_str}-topics.jsonl."""
        monkeypatch.setattr(bridge, "TOPICS_DIR", tmp_path / "topics")
        result_path = bridge.save_topics_jsonl([topic], date_str="2026-07-12")
        expected = tmp_path / "topics" / "2026-07-12-topics.jsonl"
        assert result_path == expected
        assert expected.exists()

    def test_appends_to_existing_file(self, monkeypatch, tmp_path, topic):
        """Calling twice with different topics => both topics in file."""
        monkeypatch.setattr(bridge, "TOPICS_DIR", tmp_path / "topics")
        topic1 = dict(topic, id="topic_001")
        topic2 = dict(topic, id="topic_002")
        bridge.save_topics_jsonl([topic1], date_str="2026-07-12")
        bridge.save_topics_jsonl([topic2], date_str="2026-07-12")
        lines = (tmp_path / "topics" / "2026-07-12-topics.jsonl").read_text().strip().split("\n")
        assert len(lines) == 2

    def test_skips_duplicate_ids(self, monkeypatch, tmp_path, topic):
        """Topic with same ID in existing file => not duplicated."""
        monkeypatch.setattr(bridge, "TOPICS_DIR", tmp_path / "topics")
        bridge.save_topics_jsonl([topic], date_str="2026-07-12")
        bridge.save_topics_jsonl([topic], date_str="2026-07-12")  # same topic again
        lines = (tmp_path / "topics" / "2026-07-12-topics.jsonl").read_text().strip().split("\n")
        assert len(lines) == 1

    def test_skips_duplicate_among_multiple_new(self, monkeypatch, tmp_path, topic):
        """Dedup works: one duplicate + one new => only new appended."""
        monkeypatch.setattr(bridge, "TOPICS_DIR", tmp_path / "topics")
        bridge.save_topics_jsonl([topic], date_str="2026-07-12")
        topic2 = dict(topic, id="topic_002")
        bridge.save_topics_jsonl([topic, topic2], date_str="2026-07-12")
        lines = (tmp_path / "topics" / "2026-07-12-topics.jsonl").read_text().strip().split("\n")
        assert len(lines) == 2

    def test_creates_directory_if_not_exists(self, monkeypatch, tmp_path, topic):
        """TOPICS_DIR doesn't exist => created."""
        topics_dir = tmp_path / "deeply" / "nested" / "topics"
        monkeypatch.setattr(bridge, "TOPICS_DIR", topics_dir)
        bridge.save_topics_jsonl([topic], date_str="2026-07-12")
        assert topics_dir.exists()

    def test_each_line_is_valid_json(self, monkeypatch, tmp_path, topic):
        """Every line in output file parses as JSON."""
        monkeypatch.setattr(bridge, "TOPICS_DIR", tmp_path / "topics")
        topics = [
            dict(topic, id="topic_001"),
            dict(topic, id="topic_002"),
            dict(topic, id="topic_003"),
        ]
        bridge.save_topics_jsonl(topics, date_str="2026-07-12")
        with open(tmp_path / "topics" / "2026-07-12-topics.jsonl") as f:
            for line in f:
                line = line.strip()
                if line:
                    parsed = json.loads(line)
                    assert "id" in parsed
                    assert "title" in parsed

    def test_default_date_str_used_when_none(self, monkeypatch, tmp_path, topic):
        """When date_str=None, uses datetime.utcnow().strftime('%Y-%m-%d')."""
        monkeypatch.setattr(bridge, "TOPICS_DIR", tmp_path / "topics")
        result_path = bridge.save_topics_jsonl([topic], date_str=None)
        # Should save with today's date
        assert result_path.name.endswith("-topics.jsonl")
        assert result_path.exists()


class TestLoadLatestSkeletons:
    """Tests for bridge.load_latest_skeletons()."""

    def test_returns_most_recent_skeletons(self, monkeypatch, tmp_path):
        """Multiple report dirs => returns from most recent."""
        recon_dir = tmp_path / "recon"
        monkeypatch.setattr(bridge, "RECON_DATA_DIR", recon_dir)

        # Create older report
        old_dir = recon_dir / "reports" / "20260712_120000_job1"
        old_dir.mkdir(parents=True)
        old_data = [{"creator_username": "old_creator"}]
        (old_dir / "skeletons.json").write_text(json.dumps(old_data))

        # Create newer report (sorted reverse, so alphabetically later = newer)
        new_dir = recon_dir / "reports" / "20260713_120000_job2"
        new_dir.mkdir(parents=True)
        new_data = [{"creator_username": "new_creator"}]
        (new_dir / "skeletons.json").write_text(json.dumps(new_data))

        result = bridge.load_latest_skeletons()
        assert len(result) == 1
        assert result[0]["creator_username"] == "new_creator"

    def test_no_reports_returns_empty(self, monkeypatch, tmp_path):
        """No reports dir => []."""
        recon_dir = tmp_path / "recon"
        monkeypatch.setattr(bridge, "RECON_DATA_DIR", recon_dir)
        assert bridge.load_latest_skeletons() == []

    def test_skips_dirs_without_skeletons(self, monkeypatch, tmp_path):
        """Dir with no skeletons.json => skipped, next dir tried."""
        recon_dir = tmp_path / "recon"
        monkeypatch.setattr(bridge, "RECON_DATA_DIR", recon_dir)

        # Create a dir without skeletons.json
        no_skeleton_dir = recon_dir / "reports" / "20260713_120000_job2"
        no_skeleton_dir.mkdir(parents=True)

        # Create a dir with skeletons.json (should be found)
        has_skeleton_dir = recon_dir / "reports" / "20260712_120000_job1"
        has_skeleton_dir.mkdir(parents=True)
        (has_skeleton_dir / "skeletons.json").write_text(json.dumps([{"creator_username": "found_creator"}]))

        result = bridge.load_latest_skeletons()
        assert len(result) == 1
        assert result[0]["creator_username"] == "found_creator"

    def test_empty_reports_dir_returns_empty(self, monkeypatch, tmp_path):
        """Empty reports dir => []."""
        recon_dir = tmp_path / "recon"
        monkeypatch.setattr(bridge, "RECON_DATA_DIR", recon_dir)
        reports_dir = recon_dir / "reports"
        reports_dir.mkdir(parents=True)
        assert bridge.load_latest_skeletons() == []

    def test_returns_multiple_skeletons_from_latest(self, monkeypatch, tmp_path):
        """Latest report can have multiple skeletons."""
        recon_dir = tmp_path / "recon"
        monkeypatch.setattr(bridge, "RECON_DATA_DIR", recon_dir)

        report_dir = recon_dir / "reports" / "20260713_120000_job"
        report_dir.mkdir(parents=True)
        skeletons_data = [
            {"creator_username": "creator_a", "views": 1000},
            {"creator_username": "creator_b", "views": 2000},
        ]
        (report_dir / "skeletons.json").write_text(json.dumps(skeletons_data))

        result = bridge.load_latest_skeletons()
        assert len(result) == 2

    def test_missing_reports_dir_returns_empty(self, monkeypatch, tmp_path):
        """RECON_DATA_DIR/reports doesn't exist => []."""
        recon_dir = tmp_path / "recon"
        monkeypatch.setattr(bridge, "RECON_DATA_DIR", recon_dir)
        # Don't create reports dir at all
        assert bridge.load_latest_skeletons() == []
