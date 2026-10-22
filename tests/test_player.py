"""Tests for the audio player layer."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import numpy as np

from purrd import player


def _make_pcm(duration_s: float = 0.01) -> bytes:
    """Generate a tiny PCM buffer for testing."""
    samples = int(player.SR * duration_s)
    return np.zeros(samples, dtype="<i2").tobytes()


def _make_tone(duration_s: float, freq: int = 440, amplitude: float = 1.0) -> bytes:
    """Generate a simple sine tone PCM buffer for testing."""
    t = np.linspace(0.0, duration_s, int(player.SR * duration_s), endpoint=False)
    # Start at the positive peak so the first sample is not zero.
    samples = (np.sin(2.0 * np.pi * freq * t + np.pi / 2) * amplitude * 32767).astype("<i2")
    return samples.tobytes()


def test_play_loop_variation_calls_make_pcm_until_stop() -> None:
    """play_loop_variation keeps asking for new tracks until stop is set."""
    stop = threading.Event()
    call_count = 0

    def make_pcm() -> bytes:
        nonlocal call_count
        call_count += 1
        if call_count >= 3:
            stop.set()
        return _make_pcm()

    fake_proc = MagicMock()
    fake_proc.stdin = MagicMock()
    fake_proc.wait = MagicMock()
    fake_proc.kill = MagicMock()
    fake_proc.terminate = MagicMock()

    with patch("purrd.player._player_command", return_value=["cat"]):
        with patch("subprocess.Popen", return_value=fake_proc) as popen_mock:
            player.play_loop_variation(make_pcm, stop, chunk_frames=256)

    popen_mock.assert_called_once()
    assert call_count >= 3


def test_fade_out_reduces_amplitude() -> None:
    """_fade_out brings the last sample close to zero."""
    pcm = _make_tone(0.1, amplitude=1.0)
    faded = player._fade_out(pcm)
    samples = np.frombuffer(faded, dtype="<i2")
    assert samples[0] > 1000
    assert abs(samples[-1]) <= 10


def test_fade_in_increases_amplitude() -> None:
    """_fade_in brings the first sample close to zero and the last to full."""
    pcm = _make_tone(0.1, amplitude=1.0)
    faded = player._fade_in(pcm)
    samples = np.frombuffer(faded, dtype="<i2")
    assert abs(samples[0]) <= 10
    assert samples[-1] > 1000


def test_crossfade_mixes_fade_out_and_fade_in() -> None:
    """_crossfade combines a fade-out tail with a fade-in head."""
    tail = _make_tone(0.1, freq=440, amplitude=1.0)
    head = _make_tone(0.1, freq=880, amplitude=1.0)
    mixed = player._crossfade(tail, head)
    assert len(mixed) == min(len(tail), len(head)) - (min(len(tail), len(head)) % 2)
    samples = np.frombuffer(mixed, dtype="<i2")
    # The middle should be roughly the sum of two moderate amplitudes; start
    # near the tail's full level and end near the head's full level.
    assert abs(samples[0]) > 1000
    assert abs(samples[-1]) > 1000


def test_crossfade_handles_empty_buffer() -> None:
    """_crossfade returns the concatenation when one input is empty."""
    pcm = _make_tone(0.05)
    assert player._crossfade(b"", pcm) == pcm
    assert player._crossfade(pcm, b"") == pcm


def test_play_loop_variation_pregenerates_and_crossfades() -> None:
    """The next track is generated while the current one plays and crossfaded in."""
    stop = threading.Event()
    durations = [0.5, 0.5, 0.5]
    call_count = 0

    def make_pcm() -> bytes:
        nonlocal call_count
        call_count += 1
        if call_count >= 3:
            stop.set()
        return _make_tone(durations[call_count - 1])

    fake_proc = MagicMock()
    fake_proc.stdin = MagicMock()
    fake_proc.wait = MagicMock()
    fake_proc.kill = MagicMock()
    fake_proc.terminate = MagicMock()

    with patch("purrd.player._player_command", return_value=["cat"]):
        with patch("subprocess.Popen", return_value=fake_proc):
            player.play_loop_variation(make_pcm, stop, chunk_frames=256)

    # Three tracks should have been generated, including the pre-generated one.
    assert call_count >= 3
    # Something should have been written (body + crossfade + next body).
    assert fake_proc.stdin.write.call_count > 0


def test_play_loop_variation_survives_generation_failure() -> None:
    """If make_pcm fails once, playback loops the current track instead of stopping."""
    stop = threading.Event()
    call_count = 0

    def make_pcm() -> bytes:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("render failed")
        if call_count >= 4:
            stop.set()
        return _make_pcm(0.1)

    fake_proc = MagicMock()
    fake_proc.stdin = MagicMock()
    fake_proc.wait = MagicMock()
    fake_proc.kill = MagicMock()
    fake_proc.terminate = MagicMock()

    with patch("purrd.player._player_command", return_value=["cat"]):
        with patch("subprocess.Popen", return_value=fake_proc):
            player.play_loop_variation(make_pcm, stop, chunk_frames=256)

    # It should keep trying and eventually reach the stop condition.
    assert call_count >= 4


def test_fade_helpers_ignore_odd_byte_lengths() -> None:
    """Odd-length byte buffers are rounded down to whole samples safely."""
    pcm = _make_tone(0.01)
    odd = pcm[:-1]
    assert len(player._fade_out(odd)) == len(odd) - (len(odd) % 2)
    assert len(player._fade_in(odd)) == len(odd) - (len(odd) % 2)
