"""Tests for the pre-generated ambience bank (bank.py + runner._next_pcm)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from purrd import bank, cli, runner


def _pcm(samples) -> bytes:
    return np.asarray(samples, dtype=np.int16).astype("<i2").tobytes()


def _rms_dbfs(pcm: bytes) -> float:
    s = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
    rms = float(np.sqrt(np.mean(s**2)))
    return 20.0 * np.log10(rms / 32768.0) if rms else float("-inf")


def _peak_dbfs(pcm: bytes) -> float:
    s = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
    peak = float(np.max(np.abs(s))) if s.size else 0.0
    return 20.0 * np.log10(peak / 32768.0) if peak else float("-inf")


def test_list_bank_empty_when_directory_absent(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PURRD_BANK_DIR", str(tmp_path / "nope"))
    assert bank.list_bank() == []


def test_list_bank_empty_when_directory_unreadable(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(bank._paths, "bank_dir", lambda: tmp_path)
    with patch.object(Path, "iterdir", side_effect=OSError("unreadable")):
        assert bank.list_bank() == []


def test_list_bank_filters_by_suffix_and_ignores_directories(tmp_path: Path, monkeypatch):
    bank_dir = tmp_path / "bank"
    bank_dir.mkdir()
    # Accepted audio files, intentionally unordered on disk.
    (bank_dir / "zeta.flac").write_bytes(b"")
    (bank_dir / "alpha.mp3").write_bytes(b"")
    (bank_dir / "mid.wav").write_bytes(b"")
    # Ignored: a non-audio file, an extensionless file, and a subdirectory.
    (bank_dir / "notes.txt").write_bytes(b"")
    (bank_dir / "README").write_bytes(b"")
    (bank_dir / "sub").mkdir()
    (bank_dir / "sub" / "inner.mp3").write_bytes(b"")
    monkeypatch.setenv("PURRD_BANK_DIR", str(bank_dir))
    assert bank.list_bank() == [
        bank_dir / "alpha.mp3",
        bank_dir / "mid.wav",
        bank_dir / "zeta.flac",
    ]


def test_pick_track_zero_ratio_always_none(monkeypatch):
    files = [Path("/bank/a.mp3"), Path("/bank/b.wav"), Path("/bank/c.flac")]
    monkeypatch.setattr(bank, "list_bank", lambda: files)
    for _ in range(200):
        assert bank.pick_track(0.0) is None


def test_pick_track_full_ratio_returns_a_bank_file(monkeypatch):
    files = [Path("/bank/a.mp3"), Path("/bank/b.wav"), Path("/bank/c.flac")]
    monkeypatch.setattr(bank, "list_bank", lambda: files)
    for _ in range(100):
        assert bank.pick_track(1.0) in files


def test_pick_track_full_ratio_empty_bank_none(monkeypatch):
    monkeypatch.setattr(bank, "list_bank", lambda: [])
    for _ in range(100):
        assert bank.pick_track(1.0) is None


def test_pick_track_clamps_ratio(monkeypatch):
    files = [Path("/bank/a.mp3")]
    monkeypatch.setattr(bank, "list_bank", lambda: files)
    # 2.0 behaves like 1.0: always a file.
    for _ in range(100):
        assert bank.pick_track(2.0) in files
    # -1.0 behaves like 0.0: never a file.
    for _ in range(100):
        assert bank.pick_track(-1.0) is None


@pytest.mark.parametrize(
    ("cfg", "expected"),
    [
        ({"bank": {"ratio": 0.25}}, 0.25),
        ({"bank": {"ratio": 1}}, 1.0),
        ({}, 0.0),
        ({"bank": {}}, 0.0),
        ({"bank": {"ratio": "nope"}}, 0.0),
        ({"bank": {"ratio": 2.0}}, 1.0),
        ({"bank": {"ratio": -0.5}}, 0.0),
        ({"bank": {"ratio": True}}, 0.0),
    ],
)
def test_bank_ratio_reads_config(monkeypatch, cfg, expected):
    monkeypatch.setattr(bank.config, "load", lambda: cfg)
    assert bank.bank_ratio() == expected


def test_next_pcm_zero_ratio_synthesizes(monkeypatch):
    monkeypatch.setattr(bank, "bank_ratio", lambda: 0.0)
    with (
        patch.object(runner, "_render", return_value=b"SYNTH") as render_mock,
        patch.object(bank, "decode_pcm") as decode_mock,
    ):
        assert runner._next_pcm(80, 16, 0, "classic", True, 1.0) == b"SYNTH"
    render_mock.assert_called_once_with(80, 16, 0, "classic", 1.0)
    decode_mock.assert_not_called()


def test_next_pcm_full_ratio_returns_decoded_bank_bytes(monkeypatch):
    fake_path = Path("/bank/a.mp3")
    monkeypatch.setattr(bank, "bank_ratio", lambda: 1.0)
    monkeypatch.setattr(bank, "list_bank", lambda: [fake_path])
    with (
        patch.object(runner, "_render", return_value=b"SYNTH") as render_mock,
        patch.object(bank, "decode_pcm", return_value=b"RAWPCM") as decode_mock,
    ):
        assert runner._next_pcm(80, 16, 0, "classic", True, 1.0) == b"RAWPCM"
    decode_mock.assert_called_once_with(fake_path)
    render_mock.assert_not_called()


def test_next_pcm_empty_decode_falls_back_to_synth(monkeypatch):
    fake_path = Path("/bank/a.mp3")
    monkeypatch.setattr(bank, "bank_ratio", lambda: 1.0)
    monkeypatch.setattr(bank, "list_bank", lambda: [fake_path])
    with (
        patch.object(runner, "_render", return_value=b"SYNTH") as render_mock,
        patch.object(bank, "decode_pcm", return_value=b"") as decode_mock,
    ):
        assert runner._next_pcm(80, 16, 0, "classic", True, 1.0) == b"SYNTH"
    decode_mock.assert_called_once_with(fake_path)
    render_mock.assert_called_once_with(80, 16, 0, "classic", 1.0)


def test_normalise_pcm_loud_buffer_attenuated_to_target():
    rng = np.random.default_rng(1)
    # Hot noise: RMS well above the target, peaking at full scale.
    pcm = _pcm((rng.standard_normal(44100) * 30000).astype(np.int16))
    assert _rms_dbfs(pcm) > bank.TARGET_RMS_DBFS + 1.0
    out = bank.normalise_pcm(pcm)
    assert len(out) == len(pcm)
    assert abs(_rms_dbfs(out) - bank.TARGET_RMS_DBFS) < 0.5


def test_normalise_pcm_quiet_buffer_raised_to_target():
    rng = np.random.default_rng(2)
    # Quiet noise: RMS far below the target, nowhere near clipping.
    pcm = _pcm((rng.standard_normal(44100) * 100).astype(np.int16))
    assert _rms_dbfs(pcm) < bank.TARGET_RMS_DBFS - 1.0
    out = bank.normalise_pcm(pcm)
    assert len(out) == len(pcm)
    assert abs(_rms_dbfs(out) - bank.TARGET_RMS_DBFS) < 0.5


def test_normalise_pcm_peak_held_below_ceiling_when_gain_would_clip():
    # A low-RMS spike: the RMS-matched gain would push the spike past
    # -1.0 dBFS, so the peak limit must win.
    samples = np.zeros(44100, dtype=np.int16)
    samples[1000] = -3000
    samples[2000] = 32000
    samples[3000] = -3000
    out = bank.normalise_pcm(_pcm(samples))
    assert _peak_dbfs(out) <= bank.MAX_PEAK_DBFS + 1e-9


def test_normalise_pcm_empty_and_silent_unchanged():
    assert bank.normalise_pcm(b"") == b""
    silent = _pcm(np.zeros(1024, dtype=np.int16))
    assert bank.normalise_pcm(silent) == silent


def test_next_pcm_volume_halves_bank_samples(monkeypatch):
    fake_path = Path("/bank/a.mp3")
    samples = np.array([1000, -1000, 3000, -3000], dtype=np.int16)
    pcm = _pcm(samples)
    monkeypatch.setattr(bank, "bank_ratio", lambda: 1.0)
    monkeypatch.setattr(bank, "list_bank", lambda: [fake_path])
    with (
        patch.object(runner, "_render", return_value=b"SYNTH"),
        patch.object(bank, "decode_pcm", return_value=pcm),
    ):
        assert runner._next_pcm(80, 16, 0, "classic", True, 0.5) == _pcm(samples // 2)


def test_decode_pcm_roundtrip(tmp_path: Path):
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available")
    wav = tmp_path / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.2", str(wav)],
        check=True,
        capture_output=True,
    )
    pcm = bank.decode_pcm(wav)
    assert len(pcm) > 0
    assert len(pcm) % 2 == 0


def test_decode_pcm_missing_input_returns_empty(tmp_path: Path):
    assert bank.decode_pcm(tmp_path / "nope.mp3") == b""


def test_decode_pcm_returns_empty_when_ffmpeg_absent(tmp_path: Path):
    # No ffmpeg on PATH: subprocess.run raises, decode_pcm must degrade to b"".
    with patch.object(bank.subprocess, "run", side_effect=OSError("ffmpeg not found")):
        assert bank.decode_pcm(tmp_path / "a.mp3") == b""


def test_cli_bank_ratio_writes_config_and_reads_back(tmp_path: Path, monkeypatch):
    from purrd import _paths

    cfg_dir = tmp_path / "config"
    monkeypatch.setattr(_paths, "config_dir", lambda: cfg_dir)
    monkeypatch.setenv("PURRD_BANK_DIR", str(tmp_path / "nope"))
    assert cli.main(["bank", "ratio", "0.7"]) == 0
    assert bank.bank_ratio() == 0.7


def test_cli_bank_ratio_clamps_to_one(tmp_path: Path, monkeypatch):
    from purrd import _paths

    cfg_dir = tmp_path / "config"
    monkeypatch.setattr(_paths, "config_dir", lambda: cfg_dir)
    monkeypatch.setenv("PURRD_BANK_DIR", str(tmp_path / "nope"))
    assert cli.main(["bank", "ratio", "2"]) == 0
    assert bank.bank_ratio() == 1.0


def test_cli_bank_ratio_invalid_float_exits_nonzero(tmp_path: Path, monkeypatch, capsys):
    from purrd import _paths

    cfg_dir = tmp_path / "config"
    monkeypatch.setattr(_paths, "config_dir", lambda: cfg_dir)
    monkeypatch.setenv("PURRD_BANK_DIR", str(tmp_path / "nope"))
    assert cli.main(["bank", "ratio", "abc"]) != 0
    assert "abc" in capsys.readouterr().err
