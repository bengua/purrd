"""Tests for the widget-free studio logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from purrd.studio import logic


def test_generate_loop_presets_produces_ten_distinct_entries():
    presets = logic.generate_loop_presets(count=10)
    assert len(presets) == 10
    seeds = {p["seed"] for p in presets}
    assert len(seeds) == 10
    for p in presets:
        assert 78 <= p["bpm"] <= 92
        assert p["seconds"] == 32
        assert "style" not in p


def test_generate_loop_presets_with_style_pool():
    presets = logic.generate_loop_presets(count=10, style_pool=("chill", "drive"))
    assert len(presets) == 10
    styles = {p["style"] for p in presets}
    assert styles <= {"chill", "drive"}


def test_preview_loop_params_returns_pcm_bytes():
    pcm = logic.preview_loop_params(seed=1, bpm=86, seconds=1)
    assert isinstance(pcm, bytes)
    assert len(pcm) > 0


def test_preview_loop_params_accepts_style():
    pcm = logic.preview_loop_params(seed=1, bpm=86, seconds=1, style="chill")
    assert isinstance(pcm, bytes)
    assert len(pcm) > 0


def test_voice_events_vocabulary():
    assert logic.VOICE_EVENTS == ("start", "done", "permission", "error")


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Redirect the favorites config directory into a temp path."""
    from purrd import _paths

    cfg_dir = tmp_path / "config" / _paths.APP_NAME
    monkeypatch.setattr(_paths, "config_dir", lambda: cfg_dir)


def test_remove_favorite_forwards_style(isolated_config):
    logic.add_favorite(7, 84, 16, style="chill")
    assert len(logic.list_favorites()) == 1
    logic.remove_favorite(7, 84, 16, style="chill")
    assert logic.list_favorites() == []


def test_generate_loop_presets_forwards_progress_callback():
    calls: list[tuple[int, int]] = []
    logic.generate_loop_presets(count=3, progress=lambda d, t: calls.append((d, t)))
    assert calls == [(1, 3), (2, 3), (3, 3)]


def test_preview_sound_for_event_without_active_pack(tmp_path: Path, monkeypatch):
    from purrd import _paths

    monkeypatch.setattr(_paths, "data_dir", lambda: tmp_path)
    assert logic.preview_sound_for_event("start") is None
