"""Optional voice-on-events layer.

Short spoken samples are triggered by Claude Code events and played *over* the
running music.  Sounds are sourced from an active CESP voice pack.

This module is a sibling to ``player.py``: it performs audio output, but it does
not generate signals.  It is the only place where voice playback side effects
live.
"""

from __future__ import annotations

import subprocess
import threading
import wave
from pathlib import Path

from purrd import cesp
from purrd.player import _player_command

#: Subprocess currently playing a voice sample (protected by :data:`_voice_lock`).
_voice_proc: subprocess.Popen | None = None
_voice_lock = threading.Lock()

#: Supported voice events.  Adding an event here is enough for the core; the
#: corresponding category mapping must be added in :mod:`purrd.cesp`.
EVENTS = frozenset({"start", "done", "permission", "error"})

#: Default language used when none is supplied.
DEFAULT_LANG = "en"


def play_event(event: str, lang: str = DEFAULT_LANG) -> subprocess.Popen | None:
    """Play a sound for ``event`` from the active CESP pack.

    Playback is non-blocking: the subprocess is detached so the music keeps
    running underneath.  Missing files or packs are silently ignored.

    Args:
        event: One of :data:`EVENTS`.
        lang: Language code (kept for API compatibility).

    Returns:
        The running player subprocess, or ``None`` if nothing was played.
    """
    del lang  # CESP packs carry their own language in the manifest.

    if event not in EVENTS:
        raise ValueError(f"Unknown event {event!r}; expected one of: {sorted(EVENTS)}")

    pack = cesp.get_active_pack()
    if pack is None:
        pack = cesp.ensure_default_pack()
    if pack is None:
        return None

    path = cesp.random_sound_for_event(pack, event)
    if path is not None and path.exists():
        return _play_wav(path)
    return None


def _feed_stdin(proc: subprocess.Popen, data: bytes) -> None:
    """Write ``data`` to ``proc.stdin`` and close it in the background."""

    def _write() -> None:
        try:
            if proc.stdin is not None:
                proc.stdin.write(data)
        except (BrokenPipeError, OSError):
            pass
        finally:
            try:
                if proc.stdin is not None:
                    proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass

    threading.Thread(target=_write, daemon=True).start()


def _play_wav(path: Path) -> subprocess.Popen:
    """Stream a WAV file's sample data to the system player without blocking.

    The WAV is expected to be 16-bit / 44.1 kHz / mono, matching the format
    produced by ``purrd.cesp.import_pack``. Only raw sample bytes are sent;
    the RIFF/WAVE header is stripped off.

    Returns:
        The running player subprocess so callers can stop it if needed.
    """
    global _voice_proc

    with wave.open(str(path), "rb") as wav_file:
        frames = wav_file.readframes(wav_file.getnframes())

    proc = subprocess.Popen(
        _player_command(),
        stdin=subprocess.PIPE,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    with _voice_lock:
        _voice_proc = proc
    _feed_stdin(proc, frames)
    return proc


def stop_voice() -> None:
    """Stop any voice sample currently playing.

    A short grace period lets the player drain its buffer before being killed,
    so the end of a short phrase is not cut off abruptly.
    """
    global _voice_proc

    with _voice_lock:
        proc = _voice_proc
        _voice_proc = None

    if proc is None:
        return

    try:
        proc.terminate()
        try:
            proc.wait(timeout=0.4)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    except (ProcessLookupError, OSError):
        pass
