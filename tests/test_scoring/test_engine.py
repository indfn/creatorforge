"""
Tests for agent_core.scoring.engine — scoring engine unit tests.

All 4 scoring criteria (ICP relevance, timeliness, content gap,
proof potential), weighted total calculation, competitor view bonuses,
helper functions, and load_brain_context edge cases.
"""

import json
import pytest

from agent_core.scoring import engine


# ── Shared test data ────────────────────────────────────────────────

brain_ctx = {
    "icp_keywords": [
        "revenue", "scaling", "remote", "productivity",
        "automation", "automating", "processes",
    ],
    "pillar_keywords": {
        "AI Automation": ["automation", "AI", "workflow"],
        "Growth Hacking": ["growth", "viral", "traffic", "hacking"],
    },
    "learning_weights": {
        "icp_relevance": 1.0,
        "timeliness": 1.0,
        "content_gap": 1.0,
        "proof_potential": 1.0,
    },
    "competitor_handles": ["testcreator"],
}

# ICP relevance test cases: (text, expected_score, description)
ICP_RELEVANCE_CASES = [
    ("", 3, "empty text"),
    ("cooking recipes and food", 3, "zero keyword matches"),
    ("automation workflow", 7, "few matches (automation=icp+pillar, workflow=pillar → 3)"),
    ("automation workflow AI growth", 7, "moderate (3 icp/pillar + growth=pillar → 4)"),
    ("automation workflow AI growth viral traffic", 8, "many (6 total matches)"),
    (
        "automation workflow AI growth viral traffic hacking productivity",
        9,
        "max (8 total matches, 7+ tier)",
    ),
]

# Content gap test cases: (text, expected_score, description)
CONTENT_GAP_CASES = [
    ("unrelated topic about cooking", 6, "no pillar keyword match"),
    ("AI automation workflow", 8, "pillar match via automation"),
    ("grow traffic with viral growth hacks", 8, "pillar match via growth"),
]

# Proof potential test cases: (text, expected_score, description)
PROOF_POTENTIAL_CASES = [
    ("opinion piece about AI", 6, "opinion keyword caps at 6"),
    ("build a workflow", 7, "one or two action keywords"),
    ("build a tutorial to deploy and configure a demo", 8, "three+ action keywords"),
    ("", 5, "empty text — fallback"),
    ("build and opinion", 6, "opinion overrides action keywords"),
]


# ── Helper function tests ──────────────────────────────────────────

class TestHelpers:
    """Test _extract_stems, _count_keyword_matches, _count_pain_point_matches."""

    @pytest.mark.parametrize("text,expected", [
        ("automation", ["automation"]),
        (
            "scale revenue without adding headcount",
            ["scale", "revenue", "without", "adding", "headcount"],
        ),
        ("hi", []),
    ])
    def test_extract_stems(self, text, expected):
        assert engine._extract_stems(text) == expected

    @pytest.mark.parametrize("text,keywords,expected", [
        ("build an automation workflow", ["automation", "workflow", "docker"], 2),
        ("no matches here", ["docker", "kubernetes"], 0),
        ("automation and AUTOMATION", ["automation"], 1),
    ])
    def test_count_keyword_matches(self, text, keywords, expected):
        assert engine._count_keyword_matches(text, keywords) == expected

    @pytest.mark.parametrize("text,pain_points,expected", [
        (
            "scaling revenue and adding headcount",
            ["scaling revenue without adding headcount"],
            1,
        ),
        (
            "docker kubernetes",
            ["scaling revenue without adding headcount"],
            0,
        ),
    ])
    def test_count_pain_point_matches(self, text, pain_points, expected):
        assert engine._count_pain_point_matches(text, pain_points) == expected


# ── Score ICP Relevance tests ──────────────────────────────────────

class TestScoreICPRelevance:
    """Test score_icp_relevance with keyword match tiers and pain-point bonus."""

    @pytest.mark.parametrize("text,expected,desc", ICP_RELEVANCE_CASES)
    def test_icp_relevance_tiers(self, text, expected, desc):
        """Test scoring tiers: 0→3, 1-2→5, 3-4→7, 5-6→8, 7+→9."""
        assert engine.score_icp_relevance(text, brain_ctx) == expected

    def test_score_never_exceeds_10(self):
        """Score should cap at 10 even with many matches and pain-point bonus."""
        # Create a brain_ctx with a pain point (keyword len > 20) to allow +1 bonus
        ctx_with_pain = dict(brain_ctx)
        ctx_with_pain["icp_keywords"] = list(brain_ctx["icp_keywords"]) + [
            "scaling revenue without adding headcount",
        ]
        # Many matches + pain point bonus could exceed 10 without cap
        text = "automation workflow AI growth viral traffic hacking productivity scaling revenue"
        score = engine.score_icp_relevance(text, ctx_with_pain)
        assert score <= 10

    def test_pain_point_bonus_applied(self):
        """Two+ pain point matches add +1 to score."""
        ctx_with_pain = dict(brain_ctx)
        ctx_with_pain["icp_keywords"] = [
            "scaling revenue without adding headcount is hard",
            "automating processes across distributed teams",
        ]
        text = "scaling revenue and automating processes"
        score = engine.score_icp_relevance(text, ctx_with_pain)
        # 2 icp keyword matches (scaling, revenue — from first keyword; automating, processes — from second)
        # → tier 1-2 = score 5, then +1 pain point bonus → score 6
        assert score == 6

    def test_pain_point_bonus_with_many_matches(self):
        """Pain point bonus on already-high scores caps at 10."""
        ctx_with_pain = dict(brain_ctx)
        ctx_with_pain["icp_keywords"] = brain_ctx["icp_keywords"] + [
            "scaling revenue without adding headcount",
        ]
        text = "automation workflow AI growth viral traffic hacking productivity scaling revenue adding headcount"
        score = engine.score_icp_relevance(text, ctx_with_pain)
        # Many icp/pillar matches → tier 7+ → base score 9
        # Single pain point with 4 stem hits → only 1 point matched (< 2) → no bonus
        # Final score = 9 (capped at 10)
        assert score == 9


# ── Score Content Gap tests ────────────────────────────────────────

class TestScoreContentGap:
    """Test score_content_gap base (6) and pillar keyword bonus (+2)."""

    @pytest.mark.parametrize("text,expected,desc", CONTENT_GAP_CASES)
    def test_content_gap_scores(self, text, expected, desc):
        assert engine.score_content_gap(text, brain_ctx) == expected


# ── Score Proof Potential tests ────────────────────────────────────

class TestScoreProofPotential:
    """Test score_proof_potential with action/opinion keyword logic."""

    @pytest.mark.parametrize("text,expected,desc", PROOF_POTENTIAL_CASES)
    def test_proof_potential_scores(self, text, expected, desc):
        assert engine.score_proof_potential(text) == expected


# ── Apply Competitor Bonuses tests ─────────────────────────────────

class TestApplyCompetitorBonuses:
    """Test apply_competitor_bonuses view-threshold logic and immutability."""

    def test_high_views_above_100k(self):
        """>100K views: content_gap+2, proof_potential+1."""
        scores = {"content_gap": 6, "proof_potential": 5,
                  "icp_relevance": 7, "timeliness": 6}
        result = engine.apply_competitor_bonuses(scores, 150_000)
        assert result["content_gap"] == 8
        assert result["proof_potential"] == 6
        assert result["icp_relevance"] == 7
        assert result["timeliness"] == 6

    def test_medium_views_above_50k(self):
        """>50K and <=100K views: content_gap+1 only."""
        scores = {"content_gap": 6, "proof_potential": 5}
        result = engine.apply_competitor_bonuses(scores, 75_000)
        assert result["content_gap"] == 7
        assert result["proof_potential"] == 5

    def test_low_views_below_50k(self):
        """<=50K views: no bonuses."""
        scores = {"content_gap": 6, "proof_potential": 5}
        result = engine.apply_competitor_bonuses(scores, 10_000)
        assert result == scores

    def test_bonus_capped_at_10(self):
        """Bonuses applied to near-max scores cap at 10."""
        scores = {"content_gap": 9, "proof_potential": 9}
        result = engine.apply_competitor_bonuses(scores, 150_000)
        assert result["content_gap"] == 10
        assert result["proof_potential"] == 10

    def test_does_not_mutate_input(self):
        """Input scores dict is not modified in place."""
        original = {"content_gap": 6, "proof_potential": 5,
                    "icp_relevance": 7, "timeliness": 6}
        scores_copy = dict(original)
        engine.apply_competitor_bonuses(original, 150_000)
        assert original == scores_copy

    def test_all_criteria_preserved(self):
        """All score keys are preserved in output (not just modified ones)."""
        scores = {"content_gap": 6, "proof_potential": 5,
                  "icp_relevance": 7, "timeliness": 6}
        result = engine.apply_competitor_bonuses(scores, 150_000)
        assert set(result.keys()) == {"content_gap", "proof_potential",
                                       "icp_relevance", "timeliness"}


# ── Calculate Weighted Total tests ─────────────────────────────────

class TestCalculateWeightedTotal:
    """Test calculate_weighted_total with various weight configurations."""

    def test_equal_weights(self):
        """All weights at 1.0 → sum of all scores."""
        scores = {"icp_relevance": 7, "timeliness": 6,
                  "content_gap": 8, "proof_potential": 5}
        weights = {"icp_relevance": 1.0, "timeliness": 1.0,
                   "content_gap": 1.0, "proof_potential": 1.0}
        assert engine.calculate_weighted_total(scores, weights) == 26.0

    def test_custom_weights(self):
        """Varying weights produce correct weighted sum."""
        scores = {"icp_relevance": 7, "timeliness": 6,
                  "content_gap": 8, "proof_potential": 5}
        weights = {"icp_relevance": 2.0, "timeliness": 1.0,
                   "content_gap": 0.5, "proof_potential": 0.0}
        # 7*2 + 6*1 + 8*0.5 + 5*0 = 14 + 6 + 4 + 0 = 24.0
        assert engine.calculate_weighted_total(scores, weights) == 24.0

    def test_missing_score_key_defaults_to_zero(self):
        """Missing score keys are treated as 0."""
        scores = {"icp_relevance": 7, "timeliness": 6}
        weights = {"icp_relevance": 1.0, "timeliness": 1.0,
                   "content_gap": 1.0, "proof_potential": 1.0}
        # 7*1 + 6*1 + 0*1 + 0*1 = 13.0
        assert engine.calculate_weighted_total(scores, weights) == 13.0

    def test_result_rounded_to_one_decimal(self):
        """Result is rounded to 1 decimal place."""
        scores = {"icp_relevance": 7, "timeliness": 6,
                  "content_gap": 3, "proof_potential": 5}
        weights = {"icp_relevance": 1.0, "timeliness": 1.0,
                   "content_gap": 0.5, "proof_potential": 1.0}
        # 7 + 6 + 1.5 + 5 = 19.5
        result = engine.calculate_weighted_total(scores, weights)
        assert result == 19.5
        # Verify it's a float with simple equality
        assert isinstance(result, float)

    def test_zero_weights_omit_criteria(self):
        """Zero weight effectively removes a criterion."""
        scores = {"icp_relevance": 10, "timeliness": 10,
                  "content_gap": 10, "proof_potential": 10}
        weights = {"icp_relevance": 1.0, "timeliness": 0.0,
                   "content_gap": 0.0, "proof_potential": 0.0}
        assert engine.calculate_weighted_total(scores, weights) == 10.0


# ── Score Topic orchestrator tests ─────────────────────────────────

class TestScoreTopic:
    """Test score_topic orchestrator end-to-end."""

    def test_returns_all_required_keys(self):
        """Returned dict has all 6 scoring keys."""
        result = engine.score_topic("build automation workflow", "for startups")
        expected_keys = {"icp_relevance", "timeliness", "content_gap",
                         "proof_potential", "total", "weighted_total"}
        assert set(result.keys()) == expected_keys

    def test_all_scores_non_negative(self):
        """All scores are non-negative integers/floats."""
        result = engine.score_topic("build automation workflow", "for startups")
        for key in ("icp_relevance", "timeliness", "content_gap", "proof_potential"):
            assert result[key] >= 0
        assert result["total"] >= 0
        assert result["weighted_total"] >= 0

    def test_timeliness_passthrough(self):
        """Timeliness parameter is passed through unchanged."""
        result = engine.score_topic("test", "test", timeliness=8)
        assert result["timeliness"] == 8

    def test_default_timeliness_is_6(self):
        """Default timeliness is 6."""
        result = engine.score_topic("test", "test")
        assert result["timeliness"] == 6

    def test_total_is_sum_of_four_criteria(self):
        """Total equals sum of the four individual scores (before bonuses)."""
        result = engine.score_topic("build automation workflow", "for startups")
        four_sum = (result["icp_relevance"] + result["timeliness"]
                    + result["content_gap"] + result["proof_potential"])
        assert result["total"] == four_sum

    def test_competitor_with_high_views_applies_bonus(self):
        """Competitor with >100K views gets bonuses, affecting total."""
        result = engine.score_topic(
            "build automation workflow", "for startups",
            views=150_000, is_competitor=True,
        )
        # Verify bonuses were applied (total should be higher than without bonus)
        result_no_bonus = engine.score_topic(
            "build automation workflow", "for startups",
            views=0, is_competitor=True,
        )
        assert result["total"] > result_no_bonus["total"]

    def test_competitor_with_zero_views_no_bonus(self):
        """Competitor with 0 views gets no bonuses."""
        result = engine.score_topic(
            "build automation workflow", "for startups",
            views=0, is_competitor=True,
        )
        result_non_comp = engine.score_topic(
            "build automation workflow", "for startups",
            views=0, is_competitor=False,
        )
        assert result["total"] == result_non_comp["total"]

    def test_non_competitor_no_bonus_even_with_high_views(self):
        """Non-competitor never gets bonuses regardless of views."""
        result = engine.score_topic(
            "test", "test",
            views=150_000, is_competitor=False,
        )
        # Verify content_gap and proof_potential are not elevated from bonus
        # (hard to assert exact values since they depend on input,
        #  but they should be identical to the 0-views case)
        result_zero = engine.score_topic(
            "test", "test",
            views=0, is_competitor=False,
        )
        assert result["content_gap"] == result_zero["content_gap"]
        assert result["proof_potential"] == result_zero["proof_potential"]

    def test_competitor_flag_sensitivity(self):
        """Same input differs only by is_competitor flag (high views)."""
        with_comp = engine.score_topic(
            "build automation workflow", "for startups",
            views=150_000, is_competitor=True,
        )
        without_comp = engine.score_topic(
            "build automation workflow", "for startups",
            views=150_000, is_competitor=False,
        )
        assert with_comp != without_comp
        assert with_comp["total"] != without_comp["total"]


# ── Load Brain Context tests ───────────────────────────────────────

class TestLoadBrainContext:
    """Test load_brain_context with file system edge cases."""

    def test_missing_file_returns_defaults(self, monkeypatch, tmp_path):
        """When BRAIN_FILE does not exist, return safe defaults."""
        fake_brain = tmp_path / "agent-brain.json"
        monkeypatch.setattr(engine, "BRAIN_FILE", fake_brain)
        result = engine.load_brain_context()
        assert result["icp_keywords"] == []
        assert result["pillar_keywords"] == {}
        assert result["learning_weights"] == {
            "icp_relevance": 1.0,
            "timeliness": 1.0,
            "content_gap": 1.0,
            "proof_potential": 1.0,
        }
        assert result["competitor_handles"] == []

    def test_valid_file_parses_correctly(self, monkeypatch, tmp_path):
        """Valid brain JSON is parsed into expected structure."""
        fake_brain = tmp_path / "agent-brain.json"
        brain_data = {
            "icp": {
                "pain_points": ["struggling with scaling revenue", "high churn rates"],
                "goals": ["grow monthly recurring revenue"],
                "segments": ["SaaS founders"],
            },
            "pillars": [
                {
                    "name": "Growth Hacking",
                    "keywords": ["growth", "viral", "traffic"],
                },
            ],
            "learning_weights": {
                "icp_relevance": 2.0,
                "timeliness": 1.5,
                "content_gap": 0.5,
                "proof_potential": 0.0,
            },
            "competitors": [
                {"handle": "@CompetitorA"},
                {"handle": "competitorB"},
            ],
        }
        fake_brain.write_text(json.dumps(brain_data))
        monkeypatch.setattr(engine, "BRAIN_FILE", fake_brain)

        result = engine.load_brain_context()
        assert "struggling with scaling revenue" in result["icp_keywords"]
        assert "high churn rates" in result["icp_keywords"]
        assert "grow monthly recurring revenue" in result["icp_keywords"]
        assert "SaaS founders" in result["icp_keywords"]
        assert "Growth Hacking" in result["pillar_keywords"]
        assert result["pillar_keywords"]["Growth Hacking"] == ["growth", "viral", "traffic"]
        assert result["learning_weights"]["icp_relevance"] == 2.0
        assert result["learning_weights"]["proof_potential"] == 0.0

    def test_competitor_handles_stripped_and_lowered(self, monkeypatch, tmp_path):
        """@ prefixes removed and handles lowercased."""
        fake_brain = tmp_path / "agent-brain.json"
        brain_data = {
            "icp": {},
            "pillars": [],
            "competitors": [
                {"handle": "@TestCreator"},
                {"handle": "ANOTHER_USER"},
            ],
        }
        fake_brain.write_text(json.dumps(brain_data))
        monkeypatch.setattr(engine, "BRAIN_FILE", fake_brain)

        result = engine.load_brain_context()
        assert "testcreator" in result["competitor_handles"]
        assert "another_user" in result["competitor_handles"]
        assert "@TestCreator" not in result["competitor_handles"]

    def test_missing_sections_graceful(self, monkeypatch, tmp_path):
        """Brain JSON missing sections returns empty/fallback values."""
        fake_brain = tmp_path / "agent-brain.json"
        fake_brain.write_text(json.dumps({"icp": {}}))
        monkeypatch.setattr(engine, "BRAIN_FILE", fake_brain)

        result = engine.load_brain_context()
        assert result["icp_keywords"] == []
        assert result["pillar_keywords"] == {}
        assert result["learning_weights"]["icp_relevance"] == 1.0
        assert result["competitor_handles"] == []

    def test_no_competitors_section(self, monkeypatch, tmp_path):
        """Missing competitors section returns empty list."""
        fake_brain = tmp_path / "agent-brain.json"
        fake_brain.write_text(json.dumps({"icp": {}, "pillars": []}))
        monkeypatch.setattr(engine, "BRAIN_FILE", fake_brain)

        result = engine.load_brain_context()
        assert result["competitor_handles"] == []
