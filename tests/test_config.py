"""Tests for user configuration persistence."""

from __future__ import annotations

from purrd import config


def test_save_and_load_voice_section(isolated_config):
    config.save({"voice": {"active_pack": "peon", "volume": 0.8}})
    cfg = config.load()
    assert cfg == {"voice": {"active_pack": "peon", "volume": 0.8}}


def test_save_and_load_multiple_sections(isolated_config):
    config.save(
        {
            "voice": {"active_pack": "peon"},
            "output": {"device": "default", "buffer_ms": 50},
        }
    )
    cfg = config.load()
    assert cfg["voice"] == {"active_pack": "peon"}
    assert cfg["output"] == {"device": "default", "buffer_ms": 50}


def test_save_does_not_drop_unknown_sections(isolated_config):
    config.save({"voice": {"active_pack": "peon"}, "ui": {"theme": "dark"}})
    cfg = config.load()
    assert "voice" in cfg
    assert "ui" in cfg
    assert cfg["ui"] == {"theme": "dark"}


def test_load_returns_empty_dict_when_missing(isolated_config):
    assert config.load() == {}


def test_save_empty_config_writes_only_header(isolated_config):
    config.save({})
    text = config.config_path().read_text(encoding="utf-8")
    assert "[voice]" not in text
