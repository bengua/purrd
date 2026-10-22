"""Tests for shared filesystem paths and migration."""

from __future__ import annotations

from pathlib import Path

from purrd import _paths


def test_packs_dir_prefers_environment_variable(monkeypatch, tmp_path: Path):
    custom = tmp_path / "custom_packs"
    monkeypatch.setenv("PURRD_PACKS_DIR", str(custom))
    assert _paths.packs_dir() == custom


def test_packs_dir_defaults_to_xdg_data_home_packs(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.delenv("PURRD_PACKS_DIR", raising=False)
    assert _paths.packs_dir() == tmp_path / "data" / "purrd" / "packs"


def test_config_dir_uses_env_when_set(tmp_path: Path, monkeypatch):
    custom = tmp_path / "custom_cfg"
    monkeypatch.setenv("PURRD_CONFIG_DIR", str(custom))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert _paths.config_dir() == custom


def test_config_dir_ignores_empty_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PURRD_CONFIG_DIR", "")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert _paths.config_dir() == tmp_path / "cfg" / "purrd"


def test_config_dir_falls_back_when_env_absent(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("PURRD_CONFIG_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert _paths.config_dir() == tmp_path / "cfg" / "purrd"


def test_packs_dir_ignores_empty_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PURRD_PACKS_DIR", "")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert _paths.packs_dir() == tmp_path / "data" / "purrd" / "packs"


def test_config_dir_respects_xdg_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert _paths.config_dir() == tmp_path / "cfg" / "purrd"


def test_data_dir_respects_xdg_data_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert _paths.data_dir() == tmp_path / "data" / "purrd"


def test_migrate_legacy_packs_moves_when_only_legacy_exists(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("PURRD_PACKS_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    legacy = tmp_path / ".purrd" / "packs"
    legacy.mkdir(parents=True)
    (legacy / "marker").write_text("x")

    _paths.migrate_legacy_packs()

    assert not legacy.exists()
    assert (tmp_path / ".local" / "share" / "purrd" / "packs" / "marker").exists()
    captured = capsys.readouterr()
    assert "Migrated packs" in captured.err


def test_migrate_legacy_packs_warns_when_both_exist(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("PURRD_PACKS_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    legacy = tmp_path / ".purrd" / "packs"
    xdg = tmp_path / ".local" / "share" / "purrd" / "packs"
    legacy.mkdir(parents=True)
    xdg.mkdir(parents=True)

    _paths.migrate_legacy_packs()

    captured = capsys.readouterr()
    assert "Legacy packs left" in captured.err
    assert "No automatic merge" in captured.err


def test_migrate_legacy_packs_runs_when_purrd_packs_dir_env_empty(
    tmp_path: Path, monkeypatch, capsys
):
    monkeypatch.setenv("PURRD_PACKS_DIR", "")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    legacy = tmp_path / ".purrd" / "packs"
    legacy.mkdir(parents=True)
    (legacy / "marker").write_text("x")

    _paths.migrate_legacy_packs()

    assert not legacy.exists()
    assert (tmp_path / ".local" / "share" / "purrd" / "packs" / "marker").exists()


def test_migrate_legacy_packs_noop_when_purrd_packs_dir_env_set(
    tmp_path: Path, monkeypatch, capsys
):
    custom = tmp_path / "custom"
    custom.mkdir()
    monkeypatch.setenv("PURRD_PACKS_DIR", str(custom))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    legacy = tmp_path / ".purrd" / "packs"
    legacy.mkdir(parents=True)

    _paths.migrate_legacy_packs()

    assert legacy.exists()
    captured = capsys.readouterr()
    assert captured.err == ""
