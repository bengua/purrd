"""Audio output: convert the signal to 16-bit PCM and play it on a loop by
driving a system player (PipeWire, ALSA or ffmpeg).

This layer is the only audio *side effect*: it generates nothing, it just pushes
bytes to a player. Isolated here on purpose, so the rest of the code stays pure
and testable.
"""

from __future__ import annotations

from collections.abc import Callable
import shutil
import subprocess
import threading

import numpy as np

from .synth import SR

#: Fade-out duration when stopping the music loop (milliseconds).
FADE_OUT_MS = 400

#: Crossfade duration between tracks in auto-variation (milliseconds).
# Kept short so the downbeat stays locked to the tempo.
CROSSFADE_MS = 80

#: Start generating the next track this many seconds before the current one ends.
# This removes the silent render gap on long sessions.
PREGENERATE_BEFORE_END_S = 3 * 60


def to_pcm16(buf: np.ndarray) -> bytes:
    """Float signal (~[-1, 1]) -> little-endian 16-bit PCM, mono."""
    return (np.clip(buf, -1.0, 1.0) * 32767).astype("<i2").tobytes()


def _terminate_player(
    proc: subprocess.Popen,
    term_timeout: float = 2.0,
    kill_timeout: float = 2.0,
) -> None:
    """Gracefully terminate ``proc`` and force-kill it if necessary."""
    try:
        proc.stdin.close()
    except Exception:
        pass
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        proc.wait(timeout=term_timeout)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=kill_timeout)
    except subprocess.TimeoutExpired:
        pass


def _pw_cat_supports_raw() -> bool:
    """Check whether the installed pw-cat supports the ``-a`` (raw) flag."""
    try:
        result = subprocess.run(
            ["pw-cat", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        return "-a" in result.stdout or "--raw" in result.stdout
    except FileNotFoundError:
        return False


def _player_command() -> list[str]:
    """Pick the available player. PipeWire first, then ALSA, then ffmpeg."""
    if shutil.which("pw-cat"):
        if _pw_cat_supports_raw():
            return [
                "pw-cat",
                "-p",
                "-a",
                "--format",
                "s16",
                "--rate",
                str(SR),
                "--channels",
                "1",
                "-",
            ]
        # Older pw-cat (e.g. Debian bookworm) does not support -a; fall back
        # to aplay so the same host PipeWire socket is used via ALSA/Pulse.
        if shutil.which("aplay"):
            return ["aplay", "-q", "-f", "S16_LE", "-r", str(SR), "-c", "1", "-"]
    if shutil.which("aplay"):
        return ["aplay", "-q", "-f", "S16_LE", "-r", str(SR), "-c", "1", "-"]
    if shutil.which("ffplay"):
        return [
            "ffplay",
            "-loglevel",
            "quiet",
            "-autoexit",
            "-nodisp",
            "-f",
            "s16le",
            "-ar",
            str(SR),
            "-ac",
            "1",
            "-",
        ]
    raise RuntimeError(
        "No audio player found. Install one of: pipewire-audio (pw-cat), "
        "alsa-utils (aplay) or ffmpeg (ffplay)."
    )


def _fade_out(data: bytes) -> bytes:
    """Apply a linear fade-out to a little-endian 16-bit PCM buffer."""
    n = len(data) - (len(data) % 2)
    if n == 0:
        return data
    samples = np.frombuffer(data[:n], dtype="<i2").astype(np.float64)
    fade = np.linspace(1.0, 0.0, len(samples), endpoint=False)
    return (samples * fade).astype("<i2").tobytes()


def _fade_in(data: bytes) -> bytes:
    """Apply a linear fade-in to a little-endian 16-bit PCM buffer."""
    n = len(data) - (len(data) % 2)
    if n == 0:
        return data
    samples = np.frombuffer(data[:n], dtype="<i2").astype(np.float64)
    fade = np.linspace(0.0, 1.0, len(samples), endpoint=False)
    return (samples * fade).astype("<i2").tobytes()


def _crossfade(tail: bytes, head: bytes) -> bytes:
    """Crossfade between the end of one track and the start of the next.

    Both buffers are expected to be little-endian 16-bit PCM. The returned
    buffer has the same length as the shorter input (rounded to whole samples).
    """
    n = min(len(tail), len(head)) - (min(len(tail), len(head)) % 2)
    if n <= 0:
        return tail + head
    tail_samples = np.frombuffer(tail[:n], dtype="<i2").astype(np.float64)
    head_samples = np.frombuffer(head[:n], dtype="<i2").astype(np.float64)
    fade_out = np.linspace(1.0, 0.0, len(tail_samples), endpoint=False)
    fade_in = np.linspace(0.0, 1.0, len(head_samples), endpoint=False)
    mixed = (tail_samples * fade_out + head_samples * fade_in).astype("<i2")
    return mixed.tobytes()


def play_loop(pcm: bytes, stop: threading.Event, chunk_frames: int = 4096) -> None:
    """Play ``pcm`` on a loop until ``stop`` is set.

    We write in small chunks (checking ``stop`` between each) so playback can be
    halted almost instantly, without waiting for the track to finish. CPU cost is
    negligible: writing into the pipe pauses on its own at playback rate
    (back-pressure).

    When ``stop`` is set, a short fade-out is applied to the remaining samples
    instead of cutting the audio abruptly.
    """
    proc = subprocess.Popen(_player_command(), stdin=subprocess.PIPE)
    bytes_per_chunk = chunk_frames * 2  # 16-bit mono = 2 bytes per sample
    fade_out_bytes = int(SR * FADE_OUT_MS / 1000) * 2

    def _write(data: bytes) -> bool:
        try:
            proc.stdin.write(data)
            return True
        except (BrokenPipeError, ValueError):
            return False

    try:
        i = 0
        while True:
            while i < len(pcm):
                if stop.is_set():
                    remaining = pcm[i : i + fade_out_bytes]
                    if remaining:
                        if not _write(_fade_out(remaining)):
                            return
                    return

                chunk = pcm[i : i + bytes_per_chunk]
                if not _write(chunk):
                    return
                i += bytes_per_chunk
            i = 0
    finally:
        _terminate_player(proc)


def play_loop_variation(
    make_pcm: Callable[[], bytes], stop: threading.Event, chunk_frames: int = 4096
) -> None:
    """Play a continuous sequence of generated tracks until ``stop`` is set.

    The next track is rendered in the background while the current one plays,
    starting about three minutes before the current track ends. This removes
    the silent render gap that used to make playback drop out between tracks.

    A short crossfade at the boundary keeps the tempo locked: the downbeat of
    the new track lands exactly where the old one would have, even when both
    tracks are the same.
    """
    proc = subprocess.Popen(_player_command(), stdin=subprocess.PIPE)
    bytes_per_chunk = chunk_frames * 2
    fade_out_bytes = int(SR * FADE_OUT_MS / 1000) * 2
    crossfade_bytes = int(SR * CROSSFADE_MS / 1000) * 2
    pregenerate_bytes = int(SR * PREGENERATE_BEFORE_END_S) * 2

    def _write(data: bytes) -> bool:
        try:
            proc.stdin.write(data)
            return True
        except (BrokenPipeError, ValueError):
            return False

    def _generate_next(result: list[bytes | None]) -> None:
        try:
            result.append(make_pcm())
        except Exception:
            result.append(None)

    def _play_track_body(
        pcm: bytes,
        pregen_callback: Callable[[], None] | None,
    ) -> bool:
        """Play ``pcm`` up to the crossfade point; return False if player died."""
        body_end = max(0, len(pcm) - crossfade_bytes)
        pregen_offset = max(0, len(pcm) - pregenerate_bytes)

        # For very short tracks the pregenerate window starts immediately.
        if pregen_callback is not None and pregen_offset == 0:
            pregen_callback()
            pregen_callback = None

        for i in range(0, body_end, bytes_per_chunk):
            if stop.is_set():
                remaining = pcm[i : i + fade_out_bytes]
                if remaining:
                    if not _write(_fade_out(remaining)):
                        return False
                return False

            if pregen_callback is not None and i >= pregen_offset:
                pregen_callback()
                pregen_callback = None

            chunk = pcm[i : i + bytes_per_chunk]
            if not _write(chunk):
                return False
        return True

    try:
        current_pcm = make_pcm()
        while not stop.is_set():
            next_result: list[bytes | None] = []
            next_thread: threading.Thread | None = None

            def _start_pregen() -> None:
                nonlocal next_thread
                if next_thread is None:
                    next_thread = threading.Thread(
                        target=_generate_next, args=(next_result,), daemon=True
                    )
                    next_thread.start()

            if not _play_track_body(current_pcm, _start_pregen):
                break

            if stop.is_set():
                break

            if next_thread is not None:
                next_thread.join()

            next_pcm = next_result[0] if next_result else None

            if next_pcm is None:
                # Generation failed or the track was shorter than the pregenerate
                # window. Loop the current track so music never drops out.
                tail = current_pcm[len(current_pcm) - crossfade_bytes :]
                if tail and not _write(tail):
                    break
                continue

            # Crossfade the end of the current track into the next one.
            tail = (
                current_pcm[-crossfade_bytes:]
                if len(current_pcm) >= crossfade_bytes
                else current_pcm
            )
            head = next_pcm[:crossfade_bytes] if len(next_pcm) >= crossfade_bytes else next_pcm
            crossfaded = _crossfade(tail, head)
            if not _write(crossfaded):
                break

            current_pcm = next_pcm[len(head) :]
    finally:
        _terminate_player(proc)
