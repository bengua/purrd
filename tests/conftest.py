"""Shared pytest fixtures."""

from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch):
    """Redirect the purrd config directory into a temp path."""
    from purrd import _paths

    cfg_dir = tmp_path / "config" / _paths.APP_NAME
    monkeypatch.setattr(_paths, "config_dir", lambda: cfg_dir)
    return cfg_dir


@pytest.fixture
def synthetic_template_pack(tmp_path: Path) -> Path:
    """Return a minimal CESP pack directory suitable for template discovery.

    The pack contains a valid ``openpeon.json`` manifest with a ``session.start``
    category and a matching PCM16 WAV sound file.  The parent directory of the
    returned path can be pointed to by ``PURRD_TEMPLATE_PACKS``.
    """
    root = tmp_path / "templates"
    pack_dir = root / "peon"
    sounds_dir = pack_dir / "sounds"
    sounds_dir.mkdir(parents=True)

    manifest = {
        "name": "peon",
        "display_name": "Test Peon",
        "categories": {
            "session.start": {
                "sounds": [
                    {
                        "file": "sounds/start.wav",
                        "label": "start",
                        "sha256": "0" * 64,
                    }
                ]
            }
        },
    }
    (pack_dir / "openpeon.json").write_text(json.dumps(manifest), encoding="utf-8")

    signal = np.zeros(1000, dtype=np.int16)
    with wave.open(str(sounds_dir / "start.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(signal.tobytes())

    return pack_dir
