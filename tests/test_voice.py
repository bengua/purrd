"""Tests for the optional voice-on-events layer."""

from __future__ import annotations

import json
import subprocess
import time
import wave
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from purrd import cesp
from purrd.voice import EVENTS, _play_wav, play_event


def test_event_vocabulary_integrity():
    assert EVENTS == {"start", "done", "permission", "error"}


def test_play_event_is_silent_noop_without_active_or_bundled_pack():
    with patch.object(cesp, "get_active_pack", lambda: None):
        with patch.object(cesp, "bundled_packs_dir", lambda: None):
            with patch("subprocess.Popen") as popen_mock:
                play_event("error")
    popen_mock.assert_not_called()


def test_play_event_launches_player_for_active_cesp_pack(tmp_path: Path):
    manifest = {
        "name": "test",
        "display_name": "Test",
        "categories": {
            "session.start": {
                "sounds": [{"file": "sounds/start.wav", "label": "start", "sha256": "0" * 64}]
            }
        },
    }
    pack_dir = tmp_path / "test_pack"
    sounds_dir = pack_dir / "sounds"
    sounds_dir.mkdir(parents=True)
    with wave.open(str(sounds_dir / "start.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 64)
    (pack_dir / "openpeon.json").write_text(json.dumps(manifest))

    pack = cesp.CespPack.from_directory(pack_dir)

    with patch.object(cesp, "get_active_pack", lambda: pack):
        with patch("purrd.voice._player_command", return_value=["dummy-player"]) as cmd_mock:
            with patch("subprocess.Popen") as popen_mock:
                play_event("start")

    cmd_mock.assert_called_once()
    popen_mock.assert_called_once()
    args = popen_mock.call_args[1]
    assert args["stdin"] is not None


def test_play_event_rejects_unknown_event():
    with pytest.raises(ValueError, match="Unknown event"):
        play_event("not-an-event")


def test_play_wav_streams_only_sample_bytes(tmp_path: Path):
    sample = tmp_path / "voice.wav"
    frames = b"\x01\x02" * 100
    with wave.open(str(sample), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(frames)

    captured = bytearray()
    closed = {"value": False}

    def fake_write(data: bytes) -> int:
        captured.extend(data)
        return len(data)

    def fake_close() -> None:
        closed["value"] = True

    fake_stdin = Mock()
    fake_stdin.write = fake_write
    fake_stdin.close = fake_close

    fake_proc = Mock()
    fake_proc.stdin = fake_stdin
    fake_proc.terminate = Mock()
    fake_proc.wait = Mock(return_value=0)

    with (
        patch("subprocess.Popen", return_value=fake_proc) as popen_mock,
        patch("purrd.voice._player_command", return_value=["dummy-player"]),
    ):
        result = _play_wav(sample)

    deadline = time.monotonic() + 1.0
    while not closed["value"] and time.monotonic() < deadline:
        time.sleep(0.001)

    assert result is fake_proc
    assert bytes(captured) == frames
    assert not bytes(captured).startswith(b"RIFF")
    assert closed["value"] is True
    popen_mock.assert_called_once_with(
        ["dummy-player"],
        stdin=subprocess.PIPE,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
