"""Tests for runner orchestration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from purrd import favorites, runner


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Redirect favorites into a temp directory."""
    from purrd import _paths

    cfg_dir = tmp_path / "config" / _paths.APP_NAME
    monkeypatch.setattr(_paths, "config_dir", lambda: cfg_dir)


def test_run_with_music_uses_explicit_seed_despite_favorite(isolated_config):
    """Explicit --seed must take precedence over saved favorites."""
    favorites.add(99, 80, 16)

    with patch("purrd.runner._render") as render_mock:
        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            with patch("threading.Thread") as thread_mock:
                thread_mock.return_value = MagicMock()
                runner.run_with_music(["true"], seed=5, use_favorites=True)

    render_mock.assert_called_once_with(86, 32, 5, "classic", 1.0)


def test_run_with_music_uses_favorite_when_no_seed(isolated_config):
    """When no seed is given and favorites exist, use one."""
    favorites.add(99, 80, 16)

    with patch("purrd.runner._render") as render_mock:
        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            with patch("threading.Thread") as thread_mock:
                thread_mock.return_value = MagicMock()
                runner.run_with_music(["true"], seed=None, use_favorites=True)

    render_mock.assert_called_once_with(80, 16, 99, "classic", 1.0)


def test_run_with_music_defaults_seed_to_zero(isolated_config):
    """When no seed and no favorites, fall back to the default seed zero."""
    with patch("purrd.runner._render") as render_mock:
        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            with patch("threading.Thread") as thread_mock:
                thread_mock.return_value = MagicMock()
                runner.run_with_music(["true"], seed=None, use_favorites=True)

    render_mock.assert_called_once_with(86, 32, 0, "classic", 1.0)


def test_run_with_music_propagates_explicit_style(isolated_config):
    """Explicit --style is forwarded to the renderer and wins over the favorite."""
    favorites.add(99, 80, 16, style="chill")

    with patch("purrd.runner._render") as render_mock:
        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            with patch("threading.Thread") as thread_mock:
                thread_mock.return_value = MagicMock()
                runner.run_with_music(["true"], seed=None, style="drive", use_favorites=True)

    render_mock.assert_called_once_with(80, 16, 99, "drive", 1.0)


def test_run_with_music_uses_favorite_style_when_no_style_given(isolated_config):
    """If no explicit style is provided, the favorite's style is used."""
    favorites.add(99, 80, 16, style="noir")

    with patch("purrd.runner._render") as render_mock:
        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            with patch("threading.Thread") as thread_mock:
                thread_mock.return_value = MagicMock()
                runner.run_with_music(["true"], seed=None, use_favorites=True)

    render_mock.assert_called_once_with(80, 16, 99, "noir", 1.0)


def test_run_with_music_auto_variation_uses_variation_loop(isolated_config):
    """When auto_variation is True and no explicit seed, use play_loop_variation."""
    favorites.add(99, 80, 16)

    with patch("subprocess.run", return_value=MagicMock(returncode=0)):
        with patch("threading.Thread") as thread_mock:
            thread_mock.return_value = MagicMock()
            runner.run_with_music(["true"], seed=None, auto_variation=True)

    assert thread_mock.call_args[1]["target"] is runner.play_loop_variation


def test_run_with_music_auto_variation_disabled_uses_loop(isolated_config):
    """When auto_variation is False, use the regular play_loop."""
    favorites.add(99, 80, 16)

    with patch("subprocess.run", return_value=MagicMock(returncode=0)):
        with patch("threading.Thread") as thread_mock:
            thread_mock.return_value = MagicMock()
            runner.run_with_music(["true"], seed=None, auto_variation=False)

    assert thread_mock.call_args[1]["target"] is runner.play_loop


def test_run_with_music_auto_variation_ignored_with_explicit_seed(isolated_config):
    """Auto variation does not override an explicit seed."""
    favorites.add(99, 80, 16)

    with patch("subprocess.run", return_value=MagicMock(returncode=0)):
        with patch("threading.Thread") as thread_mock:
            thread_mock.return_value = MagicMock()
            runner.run_with_music(["true"], seed=5, auto_variation=True)

    assert thread_mock.call_args[1]["target"] is runner.play_loop
