"""Tests for favorites persistence and parameter resolution."""

from __future__ import annotations

from pathlib import Path

from purrd import _paths, favorites


def test_config_dir_respects_xdg_config_home(tmp_path: Path, monkeypatch):
    custom = tmp_path / "xdg-override"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(custom))
    assert _paths.config_dir() == custom / "purrd"


def test_config_dir_falls_back_to_home(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert _paths.config_dir() == tmp_path / ".config" / "purrd"


def test_save_and_round_trip(isolated_config):
    favorites.add(7, 84, 16)
    favorites.add(42, 90, 32)
    entries = favorites.load()
    assert len(entries) == 2
    assert {"seed": 7, "bpm": 84, "seconds": 16} in entries
    assert {"seed": 42, "bpm": 90, "seconds": 32} in entries


def test_add_avoids_duplicates(isolated_config):
    favorites.add(1, 86, 32)
    favorites.add(1, 86, 32)
    assert len(favorites.load()) == 1


def test_remove_existing(isolated_config):
    favorites.add(1, 86, 32)
    favorites.add(2, 88, 32)
    favorites.remove(1, 86, 32)
    assert favorites.load() == [{"seed": 2, "bpm": 88, "seconds": 32}]


def test_remove_nonexistent_is_noop(isolated_config):
    favorites.add(1, 86, 32)
    favorites.remove(99, 99, 99)
    assert len(favorites.load()) == 1


def test_pick_random_returns_none_when_empty(isolated_config):
    assert favorites.pick_random() is None


def test_pick_random_returns_saved_preset(isolated_config):
    favorites.add(123, 80, 16)
    picked = favorites.pick_random()
    assert picked == {"seed": 123, "bpm": 80, "seconds": 16}


def test_generate_presets_produces_distinct_entries():
    presets = favorites.generate_presets(count=10)
    assert len(presets) == 10
    seeds = {p["seed"] for p in presets}
    assert len(seeds) == 10
    for p in presets:
        assert 78 <= p["bpm"] <= 92
        assert p["seconds"] == 32
        assert "style" not in p


def test_generate_presets_draws_from_style_pool():
    presets = favorites.generate_presets(count=10, style_pool=("chill", "drive"))
    assert len(presets) == 10
    styles = {p["style"] for p in presets}
    assert styles <= {"chill", "drive"}


def test_generate_presets_invokes_progress_callback():
    calls: list[tuple[int, int]] = []
    favorites.generate_presets(count=5, progress=lambda d, t: calls.append((d, t)))
    assert calls == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]


def test_resolve_params_explicit_seed_wins(isolated_config):
    favorites.add(99, 80, 16)
    bpm, seconds, seed, style = favorites.resolve_params(86, 32, 5, use_favorites=True)
    assert (bpm, seconds, seed, style) == (86, 32, 5, "classic")


def test_resolve_params_explicit_bpm_and_seconds_override_favorite(isolated_config):
    favorites.add(99, 80, 16)
    bpm, seconds, seed, style = favorites.resolve_params(120, 64, None, use_favorites=True)
    assert (bpm, seconds, seed, style) == (120, 64, 99, "classic")


def test_resolve_params_uses_favorite_when_no_seed(isolated_config):
    favorites.add(99, 80, 16)
    bpm, seconds, seed, style = favorites.resolve_params(None, None, None, use_favorites=True)
    assert (bpm, seconds, seed, style) == (80, 16, 99, "classic")


def test_resolve_params_falls_back_to_default_when_empty(isolated_config):
    bpm, seconds, seed, style = favorites.resolve_params(86, 32, None, use_favorites=True)
    assert (bpm, seconds, seed, style) == (86, 32, 0, "classic")


def test_resolve_params_no_favorite_ignores_saved(isolated_config):
    favorites.add(99, 80, 16)
    bpm, seconds, seed, style = favorites.resolve_params(86, 32, None, use_favorites=False)
    assert (bpm, seconds, seed, style) == (86, 32, 0, "classic")


def test_resolve_params_no_favorite_keeps_explicit_seed(isolated_config):
    favorites.add(99, 80, 16)
    bpm, seconds, seed, style = favorites.resolve_params(86, 32, 7, use_favorites=False)
    assert (bpm, seconds, seed, style) == (86, 32, 7, "classic")


def test_resolve_params_explicit_style_wins(isolated_config):
    favorites.add(99, 80, 16, style="chill")
    bpm, seconds, seed, style = favorites.resolve_params(
        None, None, None, style="drive", use_favorites=True
    )
    assert (bpm, seconds, seed, style) == (80, 16, 99, "drive")


def test_resolve_params_uses_favorite_style(isolated_config):
    favorites.add(99, 80, 16, style="noir")
    bpm, seconds, seed, style = favorites.resolve_params(None, None, None, use_favorites=True)
    assert (bpm, seconds, seed, style) == (80, 16, 99, "noir")


def test_style_is_round_tripped(isolated_config):
    favorites.add(7, 84, 16, style="chill")
    entries = favorites.load()
    assert {"seed": 7, "bpm": 84, "seconds": 16, "style": "chill"} in entries


def test_classic_style_is_not_persisted_by_default(isolated_config):
    favorites.add(7, 84, 16, style="classic")
    entries = favorites.load()
    assert {"seed": 7, "bpm": 84, "seconds": 16} in entries
    assert all("style" not in e for e in entries)
