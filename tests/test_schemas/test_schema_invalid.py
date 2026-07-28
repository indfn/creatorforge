"""Test that all 17 JSON Schemas properly reject invalid data.

Each test case provides data that MUST raise ValidationError.
"""

import pytest
from jsonschema.exceptions import ValidationError


# Each case: (schema_filename, invalid_data_dict, description)
INVALID_CASES = [
    # ── Missing required fields ──────────────────────────────────────
    ("quota-budget.schema.json", {}, "quota-budget: missing all required"),
    (
        "quota-budget.schema.json",
        {"budgets": {}, "date": "2026-07-13"},
        "quota-budget: missing version",
    ),
    ("checkpoint.schema.json", {}, "checkpoint: missing all required"),
    (
        "checkpoint.schema.json",
        {"stage": "scrape"},
        "checkpoint: only stage present",
    ),
    ("pipeline-stage.schema.json", {}, "pipeline-stage: missing all required"),
    (
        "pipeline-stage.schema.json",
        {"name": "scrape", "output_schema": "x.json"},
        "pipeline-stage: missing depends_on",
    ),
    ("channel-config.schema.json", {}, "channel-config: missing all required"),
    (
        "channel-config.schema.json",
        {"channel_name": "Test"},
        "channel-config: missing brand/youtube/production",
    ),
    (
        "production-order.schema.json",
        {},
        "production-order: missing all required",
    ),
    (
        "hyperframe.schema.json",
        {},
        "hyperframe: missing all required",
    ),
    ("competitor-reel.schema.json", {}, "competitor-reel: missing all required"),
    (
        "competitor-reel.schema.json",
        {"shortcode": "abc"},
        "competitor-reel: missing url/views",
    ),
    ("angle.schema.json", {}, "angle: missing all required"),
    (
        "angle.schema.json",
        {"id": "a1", "topic_id": "t1", "format": "longform"},
        "angle: missing contrast/created_at",
    ),
    ("topic.schema.json", {}, "topic: missing all required"),
    (
        "topic.schema.json",
        {"id": "t1", "title": "Test"},
        "topic: missing source/discovered_at/scoring",
    ),
    (
        "agent-brain.schema.json",
        {},
        "agent-brain: missing all 10 required top-level keys",
    ),
    (
        "agent-brain.schema.json",
        {"identity": {"name": "T"}},
        "agent-brain: icp missing, others blank — identity alone isn't enough",
    ),
    ("hook.schema.json", {}, "hook: missing all required"),
    (
        "hook.schema.json",
        {"id": "h1", "angle_id": "a1"},
        "hook: missing platform/pattern/hook_text/score/created_at",
    ),
    (
        "swipe-hook.schema.json",
        {},
        "swipe-hook: missing all required",
    ),
    (
        "analytics-entry.schema.json",
        {},
        "analytics-entry: missing all required",
    ),
    (
        "insight.schema.json",
        {},
        "insight: missing last_updated",
    ),
    ("script.schema.json", {}, "script: missing all required"),
    (
        "script.schema.json",
        {"id": "s1"},
        "script: only id present, missing 7 other required fields",
    ),
    # ── Wrong types ──────────────────────────────────────────────────
    (
        "quota-budget.schema.json",
        {
            "budgets": "not_an_object",
            "date": "2026-07-13",
            "version": "not_an_int",
        },
        "quota-budget: budgets and version wrong types",
    ),
    (
        "checkpoint.schema.json",
        {
            "stage": 123,
            "pipeline_id": "p1",
            "status": "completed",
            "created_at": "2026-07-13T00:00:00Z",
            "content_hash": "abc",
        },
        "checkpoint: stage is int, should be string",
    ),
    (
        "pipeline-stage.schema.json",
        {
            "name": "scrape",
            "output_schema": "x.json",
            "depends_on": "not_an_array",
        },
        "pipeline-stage: depends_on should be array",
    ),
    (
        "competitor-reel.schema.json",
        {"shortcode": "abc", "url": "not-a-url", "views": -1},
        "competitor-reel: views negative (< minimum 0)",
    ),
    # ── Enum violations ──────────────────────────────────────────────
    (
        "checkpoint.schema.json",
        {
            "stage": "scrape",
            "pipeline_id": "p1",
            "status": "unknown_status",
            "created_at": "2026-07-13T00:00:00Z",
            "content_hash": "abc",
        },
        "checkpoint: status not in enum",
    ),
    (
        "angle.schema.json",
        {
            "id": "a1",
            "topic_id": "t1",
            "format": "invalid_format",
            "contrast": {
                "common_belief": "X",
                "surprising_truth": "Y",
                "contrast_strength": "moderate",
            },
            "created_at": "2026-07-13T00:00:00Z",
        },
        "angle: format not in enum",
    ),
    (
        "hook.schema.json",
        {
            "id": "h1",
            "angle_id": "a1",
            "platform": "youtube_longform",
            "pattern": "non_existent_pattern",
            "hook_text": "Test",
            "score": {
                "contrast_fit": 5,
                "pattern_strength": 5,
                "platform_fit": 5,
                "composite": 5,
            },
            "created_at": "2026-07-13T00:00:00Z",
        },
        "hook: pattern not in enum",
    ),
    # ── additionalProperties: false violations ───────────────────────
    (
        "angle.schema.json",
        {
            "id": "a1",
            "topic_id": "t1",
            "format": "longform",
            "contrast": {
                "common_belief": "X",
                "surprising_truth": "Y",
                "contrast_strength": "moderate",
            },
            "created_at": "2026-07-13T00:00:00Z",
            "extra_field": "should_not_exist",
        },
        "angle: additional property not allowed",
    ),
    (
        "hook.schema.json",
        {
            "id": "h1",
            "angle_id": "a1",
            "platform": "youtube_longform",
            "pattern": "contradiction",
            "hook_text": "Test",
            "score": {
                "contrast_fit": 5,
                "pattern_strength": 5,
                "platform_fit": 5,
                "composite": 5,
            },
            "created_at": "2026-07-13T00:00:00Z",
            "unknown_key": True,
        },
        "hook: additional property not allowed",
    ),
    (
        "analytics-entry.schema.json",
        {
            "id": "e1",
            "content_id": "c1",
            "platform": "youtube_longform",
            "analyzed_at": "2026-07-13T00:00:00Z",
            "metrics": {},
            "bogus": True,
        },
        "analytics-entry: additional property not allowed",
    ),
    # ── Pattern/format violations ────────────────────────────────────
    (
        "quota-budget.schema.json",
        {
            "budgets": {
                "test_api": {
                    "daily_limit": 1000,
                    "consumed": 0,
                    "remaining": 1000,
                }
            },
            "date": "not-a-date",
            "version": 1,
        },
        "quota-budget: date doesn't match YYYY-MM-DD pattern",
    ),
    (
        "channel-config.schema.json",
        {
            "channel_name": "Test",
            "brand": {"name": "Test", "primary_color": "invalid"},
            "youtube": {},
            "production": {"voice": "default", "profile": "default"},
        },
        "channel-config: primary_color doesn't match hex pattern",
    ),
    # ── Bound violations (minimum/maximum) ───────────────────────────
    (
        "topic.schema.json",
        {
            "id": "t1",
            "title": "Test",
            "source": {
                "platform": "youtube",
                "url": "https://example.com",
            },
            "discovered_at": "2026-07-13T00:00:00Z",
            "scoring": {
                "icp_relevance": 0,
                "timeliness": 5,
                "content_gap": 5,
                "proof_potential": 5,
                "total": 15,
                "weighted_total": 5.0,
            },
        },
        "topic: icp_relevance=0 is below minimum 1",
    ),
    (
        "hook.schema.json",
        {
            "id": "h1",
            "angle_id": "a1",
            "platform": "youtube_longform",
            "pattern": "contradiction",
            "hook_text": "Test",
            "score": {
                "contrast_fit": 15,
                "pattern_strength": 5,
                "platform_fit": 5,
                "composite": 5,
            },
            "created_at": "2026-07-13T00:00:00Z",
        },
        "hook: contrast_fit=15 exceeds maximum 10",
    ),
    # ── MinItems violation (sections in script schema) ───────────────
    (
        "script.schema.json",
        {
            "id": "s1",
            "angle_id": "a1",
            "hook_ids": ["h1"],
            "platform": "youtube_longform",
            "title": "Test",
            "estimated_duration": "5 min",
            "status": "draft",
            "created_at": "2026-07-13T00:00:00Z",
            "script_structure": {
                "opening_hook": {
                    "hook_text": "X",
                    "pattern": "contradiction",
                    "visual_direction": "Face",
                },
                "retention_hook": {
                    "text": "Y",
                    "timestamp_target": "30s",
                    "technique": "open loop",
                },
                "sections": [
                    {
                        "title": "S1",
                        "talking_points": ["A"],
                        "proof_element": "Demo",
                        "transition": "Move on",
                        "duration_estimate": "1 min",
                    },
                ],
                "mid_cta": {
                    "text": "Sub",
                    "type": "community",
                    "placement": "end",
                },
                "closing_cta": {
                    "text": "Sub",
                    "type": "community",
                    "template_source": "generated",
                },
                "outro": {
                    "subscribe_prompt": "Sub",
                    "next_video_tease": "Next",
                },
            },
        },
        "script: sections has 1 item, minimum is 3",
    ),
    # ── Phase 9 schemas ────────────────────────────────────────────────
    (
        "tts-config.schema.json",
        {},
        "tts-config: missing all required",
    ),
    (
        "tts-config.schema.json",
        {"provider": "invalid_provider", "characters": {}},
        "tts-config: provider not in enum",
    ),
    (
        "alignment.schema.json",
        {},
        "alignment: not an array",
    ),
    (
        "alignment.schema.json",
        [{}],
        "alignment: entry missing word, start, end, probability",
    ),
    (
        "alignment.schema.json",
        [{"word": "test", "start": 0, "end": 0.5, "probability": 1.5}],
        "alignment: probability exceeds maximum 1",
    ),
]


@pytest.mark.parametrize(
    "schema_name,data,desc",
    INVALID_CASES,
    ids=[c[2][:50] for c in INVALID_CASES],
)
def test_invalid(schema_name, data, desc, validator_for):
    """Invalid data must raise ValidationError."""
    with pytest.raises(ValidationError):
        validator_for(schema_name, data)
