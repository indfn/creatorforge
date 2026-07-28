"""Tests for scene rendering — HyperFrames-compliant blueprint generation and Playwright rendering."""

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_core.render.scene import render_scene, _generate_scene_blueprint


GSAP_URL = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"


class TestGenerateSceneBlueprint:
    """_generate_scene_blueprint — HyperFrames composition structure."""

    def test_generates_valid_hyperframes_html(self):
        timeline = {
            "duration": 10.0,
            "elements": [
                {"type": "text", "content": "Hello", "start": 0.0, "duration": 5.0},
            ],
        }
        config = {"render": {"width": 1920, "height": 1080, "fps": 30}}
        html = _generate_scene_blueprint("scene_01", timeline, config)
        assert "<!doctype html>" in html
        assert "Hello" in html
        assert "1920" in html
        assert "1080" in html
        assert 'data-composition-id="scene-scene_01"' in html
        assert 'data-duration="10.0"' in html
        assert GSAP_URL in html
        assert "window.__timelines" in html
        assert "gsap.timeline" in html

    def test_empty_elements_produces_valid_composition(self):
        timeline = {"duration": 5.0, "elements": []}
        config = {"render": {"width": 1920, "height": 1080, "fps": 30}}
        html = _generate_scene_blueprint("scene_01", timeline, config)
        assert "<!doctype html>" in html
        assert 'data-composition-id="scene-scene_01"' in html
        assert 'data-duration="5.0"' in html
        assert "window.__timelines" in html
        assert 'data-track-index=' not in html  # no elements → no clips

    def test_broll_element_as_direct_video_child(self):
        timeline = {
            "duration": 10.0,
            "elements": [
                {"type": "broll", "path": "/tmp/broll.mp4", "start": 0.0, "duration": 10.0},
            ],
        }
        config = {"render": {"width": 1920, "height": 1080, "fps": 30}}
        html = _generate_scene_blueprint("scene_01", timeline, config)
        assert "<video" in html
        assert '/tmp/broll.mp4' in html
        assert 'class="broll-element"' in html
        assert 'data-track-index="0"' in html
        assert 'muted playsinline' in html

    def test_image_element_in_clip(self):
        timeline = {
            "duration": 5.0,
            "elements": [
                {"type": "image", "src": "/tmp/img.png", "start": 0.0, "duration": 5.0},
            ],
        }
        config = {"render": {"width": 1920, "height": 1080, "fps": 30}}
        html = _generate_scene_blueprint("scene_01", timeline, config)
        assert 'class="clip image-element"' in html
        assert '/tmp/img.png' in html
        assert '<img' in html
        assert 'data-track-index="1"' in html

    def test_uses_default_dimensions(self):
        timeline = {"duration": 5.0, "elements": []}
        config = {}
        html = _generate_scene_blueprint("scene_01", timeline, config)
        assert "1920" in html
        assert "1080" in html

    def test_text_element_has_gsap_tween(self):
        timeline = {
            "duration": 10.0,
            "elements": [
                {"type": "text", "content": "Fade in", "start": 0.5, "duration": 5.0},
            ],
        }
        config = {"render": {"width": 1920, "height": 1080, "fps": 30}}
        html = _generate_scene_blueprint("scene_01", timeline, config)
        assert 'tl.from(' in html
        assert '#el-0' in html
        assert '"power3.out"' in html
        assert 'opacity: 0' in html or 'opacity:0' in html

    def test_gsap_timeline_paused(self):
        timeline = {"duration": 5.0, "elements": []}
        config = {"render": {"width": 1920, "height": 1080, "fps": 30}}
        html = _generate_scene_blueprint("scene_01", timeline, config)
        assert 'paused: true' in html

    def test_composition_id_matches_timeline_key(self):
        timeline = {"duration": 5.0, "elements": []}
        config = {"render": {"width": 1920, "height": 1080, "fps": 30}}
        html = _generate_scene_blueprint("scene_custom", timeline, config)
        assert 'data-composition-id="scene-scene_custom"' in html
        assert 'window.__timelines["scene-scene_custom"]' in html

    def test_no_css_keyframes_for_element_animations(self):
        timeline = {
            "duration": 5.0,
            "elements": [
                {"type": "text", "content": "No CSS keyframes", "start": 0.0, "duration": 5.0},
            ],
        }
        config = {"render": {"width": 1920, "height": 1080, "fps": 30}}
        html = _generate_scene_blueprint("scene_01", timeline, config)
        assert "@keyframes" not in html or "@keyframes scene-fade-in" not in html
        assert "requestAnimationFrame" not in html

    def test_all_element_types_get_gsap_tweens(self):
        timeline = {
            "duration": 10.0,
            "elements": [
                {"type": "text", "content": "Text", "start": 0.0, "duration": 5.0},
                {"type": "image", "src": "/img.png", "start": 2.0, "duration": 4.0},
                {"type": "broll", "path": "/broll.mp4", "start": 0.0, "duration": 10.0},
            ],
        }
        config = {"render": {"width": 1920, "height": 1080, "fps": 30}}
        html = _generate_scene_blueprint("scene_01", timeline, config)
        assert '#el-0' in html
        assert '#el-1' in html
        assert '#el-2' in html
        assert "#el-0" in html
        assert html.count("tl.from") == 3


class TestRenderScene:
    """render_scene"""

    def _mock_render(self, blueprint_path, output_path, channel_config):
        """Helper: mock _render_with_playwright that creates the output file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("mock video content", encoding="utf-8")

    def test_renders_scene_success(self, tmp_path, mock_playwright):
        production_dir = tmp_path / "production"
        production_dir.mkdir()
        timeline = {
            "duration": 5.0,
            "elements": [{"type": "text", "content": "Test", "start": 0.0, "duration": 5.0}],
        }
        config = {"render": {"width": 1920, "height": 1080, "fps": 30}}

        with patch("agent_core.render.scene._render_with_playwright", side_effect=self._mock_render):
            result = render_scene("scene_01", production_dir, config, timeline)

        assert result is not None
        assert result.exists()
        assert result.name == "scene_01.mp4"

    def test_creates_blueprint_and_scene_dirs(self, tmp_path, mock_playwright):
        production_dir = tmp_path / "production"
        production_dir.mkdir()
        timeline = {"duration": 3.0, "elements": []}
        config = {"render": {"width": 1920, "height": 1080, "fps": 30}}

        with patch("agent_core.render.scene._render_with_playwright", side_effect=self._mock_render):
            render_scene("scene_01", production_dir, config, timeline)

        assert (production_dir / "render" / "blueprints").exists()
        assert (production_dir / "render" / "scenes").exists()
        assert (production_dir / "render" / "blueprints" / "scene_01.html").exists()

    def test_returns_none_on_failure(self, tmp_path):
        production_dir = tmp_path / "production"
        production_dir.mkdir()
        timeline = {"duration": 3.0, "elements": []}
        config = {"render": {"width": 1920, "height": 1080, "fps": 30}}

        with patch("agent_core.render.scene._render_with_playwright", side_effect=Exception("fail")):
            result = render_scene("scene_01", production_dir, config, timeline)

        assert result is None
