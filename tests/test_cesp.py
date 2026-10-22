"""Tests for CESP voice-pack support."""

from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np
import pytest

from purrd import cesp


def test_load_manifest_peon(synthetic_template_pack: Path):
    manifest = cesp.load_manifest(synthetic_template_pack / "openpeon.json")
    assert manifest["name"] == "peon"
    assert "display_name" in manifest
    assert "categories" in manifest
    assert "session.start" in manifest["categories"]


def test_category_mapping():
    assert cesp.category_for_event("start") == ("session.start", "task.acknowledge")
    assert cesp.category_for_event("done") == ("task.complete",)
    assert cesp.category_for_event("permission") == ("input.required",)
    assert cesp.category_for_event("error") == ("task.error",)


def test_category_for_event_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown event"):
        cesp.category_for_event("unknown")


def test_random_sound_returns_existing_file(synthetic_template_pack: Path, tmp_path: Path):
    pack = cesp.import_pack(synthetic_template_pack, tmp_path)
    path = cesp.random_sound_for_event(pack, "start")
    assert path is not None
    assert path.exists()


def test_list_template_packs_uses_purrd_template_packs_env(
    synthetic_template_pack: Path, monkeypatch
):
    monkeypatch.setenv("PURRD_TEMPLATE_PACKS", str(synthetic_template_pack.parent))
    templates = cesp.list_template_packs()
    assert any(p.name == "peon" for p in templates)


def test_list_template_packs_skips_missing_template_root(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PURRD_TEMPLATE_PACKS", str(tmp_path / "nowhere"))
    templates = cesp.list_template_packs()
    assert isinstance(templates, list)


def test_random_sound_returns_none_for_missing_category(tmp_path: Path):
    manifest = {
        "name": "empty",
        "display_name": "Empty",
        "categories": {},
    }
    pack_dir = tmp_path / "empty"
    pack_dir.mkdir()
    (pack_dir / "openpeon.json").write_text(json.dumps(manifest))
    pack = cesp.CespPack.from_directory(pack_dir)
    assert cesp.random_sound_for_event(pack, "start") is None


def test_normalize_wav_to_44100_mono_pcm16(tmp_path: Path):
    src = tmp_path / "input.wav"
    dst = tmp_path / "output.wav"

    # Create a 22.05 kHz stereo sine wave.
    duration = 0.5
    sr = 22050
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    tone = np.sin(2 * np.pi * 440 * t)
    left = (tone * 32767).astype(np.int16)
    right = (tone * 16383).astype(np.int16)
    stereo = np.column_stack((left, right)).ravel()

    with wave.open(str(src), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(stereo.tobytes())

    cesp.normalize_audio(src, dst)

    with wave.open(str(dst), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 44100
        assert w.getnframes() > 0


def test_import_pack_rewrites_manifest_paths(synthetic_template_pack: Path, tmp_path: Path):
    pack = cesp.import_pack(synthetic_template_pack, tmp_path)
    for entry in pack.categories.values():
        for sound in entry["sounds"]:
            assert Path(sound["file"]).suffix == ".wav"
            assert (pack.pack_dir / sound["file"]).exists()


def test_active_pack_persistence(tmp_path: Path):
    manifest = {
        "name": "test",
        "display_name": "Test",
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
    pack_dir = tmp_path / "test"
    pack_dir.mkdir()
    sounds = pack_dir / "sounds"
    sounds.mkdir()

    # Write a minimal valid WAV.
    signal = np.zeros(1000, dtype=np.int16)
    with wave.open(str(sounds / "start.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(signal.tobytes())

    (pack_dir / "openpeon.json").write_text(json.dumps(manifest))

    pack = cesp.import_pack(pack_dir, tmp_path / "packs")
    cesp.set_active_pack(pack.name)

    retrieved = cesp.get_active_pack(tmp_path / "packs")
    assert retrieved is not None
    assert retrieved.name == pack.name
