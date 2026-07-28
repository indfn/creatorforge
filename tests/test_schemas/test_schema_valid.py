"""Test that all 17 JSON Schemas accept minimal valid data."""

import pytest


# Each case: (schema_filename, valid_data_dict, description)
VALID_CASES = [
    # ── Phase 1 schemas ──────────────────────────────────────────────
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
            "date": "2026-07-13",
            "version": 1,
        },
        "minimal valid quota-budget",
    ),
    (
        "checkpoint.schema.json",
        {
            "stage": "scrape",
            "pipeline_id": "pipe_001",
            "status": "completed",
            "created_at": "2026-07-13T00:00:00Z",
            "content_hash": "abc123def456",
        },
        "minimal valid checkpoint",
    ),
    (
        "pipeline-stage.schema.json",
        {
            "name": "scrape",
            "output_schema": "checkpoint.schema.json",
            "depends_on": [],
        },
        "minimal valid pipeline-stage",
    ),
    # ── Channel config ───────────────────────────────────────────────
    (
        "channel-config.schema.json",
        {
            "channel_name": "TestChannel",
            "brand": {"name": "Test Brand"},
            "youtube": {},
            "production": {"voice": "default", "profile": "default"},
        },
        "minimal valid channel-config",
    ),
    # ── Production schemas ───────────────────────────────────────────
    (
        "production-order.schema.json",
        {
            "title": "Test Episode",
            "scenes": [],
            "audio": {},
            "output": {},
        },
        "minimal valid production-order (empty scenes)",
    ),
    (
        "hyperframe.schema.json",
        {
            "scene_id": "scene_01",
            "start_time": 0.0,
            "end_time": 10.0,
            "template": "default",
            "elements": [],
        },
        "minimal valid hyperframe (empty elements)",
    ),
    # ── Recon schemas ────────────────────────────────────────────────
    (
        "competitor-reel.schema.json",
        {
            "shortcode": "abc123",
            "url": "https://instagram.com/p/abc123/",
            "views": 1000,
        },
        "minimal valid competitor-reel",
    ),
    (
        "angle.schema.json",
        {
            "id": "angle_001",
            "topic_id": "topic_001",
            "format": "longform",
            "contrast": {
                "common_belief": "People think X",
                "surprising_truth": "Actually Y is true",
                "contrast_strength": "moderate",
            },
            "created_at": "2026-07-13T00:00:00Z",
        },
        "minimal valid angle",
    ),
    (
        "topic.schema.json",
        {
            "id": "topic_001",
            "title": "Test Topic",
            "source": {
                "platform": "youtube",
                "url": "https://youtube.com/watch?v=test",
            },
            "discovered_at": "2026-07-13T00:00:00Z",
            "scoring": {
                "icp_relevance": 5,
                "timeliness": 5,
                "content_gap": 5,
                "proof_potential": 5,
                "total": 20,
                "weighted_total": 5.0,
            },
        },
        "minimal valid topic",
    ),
    # ── Agent brain ──────────────────────────────────────────────────
    (
        "agent-brain.schema.json",
        {
            "identity": {
                "name": "Test Creator",
                "brand": "TestBrand",
                "niche": "testing",
                "tone": ["educational"],
            },
            "icp": {
                "segments": ["founders"],
                "pain_points": ["time"],
                "goals": ["grow"],
            },
            "pillars": [
                {"name": "AI", "description": "AI content"},
            ],
            "platforms": {
                "research": ["youtube"],
                "posting": ["youtube"],
            },
            "competitors": [
                {"name": "Other", "platform": "youtube", "handle": "@other"},
            ],
            "cadence": {
                "weekly_schedule": {},
            },
            "monetization": {
                "primary_funnel": "community",
                "cta_strategy": {},
            },
            "learning_weights": {
                "icp_relevance": 1.0,
                "timeliness": 1.0,
                "content_gap": 1.0,
                "proof_potential": 1.0,
            },
            "hook_preferences": {
                "contradiction": 0,
                "specificity": 0,
                "timeframe_tension": 0,
                "pov_as_advice": 0,
                "vulnerable_confession": 0,
                "pattern_interrupt": 0,
            },
            "performance_patterns": {},
            "metadata": {
                "version": "1.0.0",
                "created_at": "2026-07-13T00:00:00Z",
                "updated_at": "2026-07-13T00:00:00Z",
            },
        },
        "minimal valid agent-brain",
    ),
    # ── Hook schemas ─────────────────────────────────────────────────
    (
        "hook.schema.json",
        {
            "id": "hook_001",
            "angle_id": "angle_001",
            "platform": "youtube_longform",
            "pattern": "contradiction",
            "hook_text": "Most people think X, but Y is true",
            "score": {
                "contrast_fit": 5.0,
                "pattern_strength": 5.0,
                "platform_fit": 5.0,
                "composite": 5.0,
            },
            "created_at": "2026-07-13T00:00:00Z",
        },
        "minimal valid hook",
    ),
    (
        "swipe-hook.schema.json",
        {
            "id": "swipe_001",
            "hook_text": "This one trick changed everything",
            "pattern": "contradiction",
            "why_it_works": "Curiosity gap drives clicks",
            "competitor": "TestCreator",
            "platform": "instagram_reels",
            "url": "https://instagram.com/p/test/",
            "engagement": {"views": 5000},
            "saved_at": "2026-07-13T00:00:00Z",
        },
        "minimal valid swipe-hook",
    ),
    # ── Analytics schemas ────────────────────────────────────────────
    (
        "analytics-entry.schema.json",
        {
            "id": "entry_001",
            "content_id": "content_001",
            "platform": "youtube_longform",
            "analyzed_at": "2026-07-13T00:00:00Z",
            "metrics": {},
        },
        "minimal valid analytics-entry (empty metrics)",
    ),
    (
        "insight.schema.json",
        {
            "last_updated": "2026-07-13T00:00:00Z",
        },
        "minimal valid insight",
    ),
    # ── Script (most complex) ────────────────────────────────────────
    (
        "script.schema.json",
        {
            "id": "script_001",
            "angle_id": "angle_001",
            "hook_ids": ["hook_001"],
            "platform": "youtube_longform",
            "title": "Test Script",
            "estimated_duration": "8-12 minutes",
            "status": "draft",
            "created_at": "2026-07-13T00:00:00Z",
            "script_structure": {
                "opening_hook": {
                    "hook_text": "Most people think X",
                    "pattern": "contradiction",
                    "visual_direction": "Face to camera",
                },
                "retention_hook": {
                    "text": "But here's what happens next",
                    "timestamp_target": "30s",
                    "technique": "open loop",
                },
                "sections": [
                    {
                        "title": "Section 1",
                        "talking_points": ["Point A", "Point B"],
                        "proof_element": "Demo",
                        "transition": "Now let's look at...",
                        "duration_estimate": "2-3 min",
                    },
                    {
                        "title": "Section 2",
                        "talking_points": ["Point C"],
                        "proof_element": "Data",
                        "transition": "This brings us to...",
                        "duration_estimate": "2 min",
                    },
                    {
                        "title": "Section 3",
                        "talking_points": ["Point D"],
                        "proof_element": "Case study",
                        "transition": "Here's what to do next",
                        "duration_estimate": "1-2 min",
                    },
                ],
                "mid_cta": {
                    "text": "Subscribe for more",
                    "type": "community",
                    "placement": "after section 2",
                },
                "closing_cta": {
                    "text": "Hit subscribe now",
                    "type": "community",
                    "template_source": "generated",
                },
                "outro": {
                    "subscribe_prompt": "Subscribe for more content",
                    "next_video_tease": "Next video covers Y",
                },
            },
        },
        "minimal valid script (longform with script_structure)",
    ),
    # ── Phase 9 schemas ────────────────────────────────────────────────
    (
        "tts-config.schema.json",
        {
            "provider": "gemini",
            "characters": {
                "narrator": {
                    "voice": "en-US-Neural2-A",
                    "style": "default",
                    "pace": "normal",
                    "accent": "us",
                    "profile": "default",
                },
            },
        },
        "minimal valid tts-config",
    ),
    (
        "alignment.schema.json",
        [
            {
                "word": "Hello",
                "start": 0.0,
                "end": 0.3,
                "probability": 0.95,
            },
        ],
        "minimal valid alignment entry",
    ),
]


@pytest.mark.parametrize(
    "schema_name,data,desc",
    VALID_CASES,
    ids=[c[2] for c in VALID_CASES],
)
def test_valid(schema_name, data, desc, validator_for):
    """A minimal valid fixture must validate without error."""
    validator_for(schema_name, data)  # raises if invalid
