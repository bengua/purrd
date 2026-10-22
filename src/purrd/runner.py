"""Orchestration — the heart of purrd.

Two uses:
  * ``run_with_music(cmd)`` : play music WHILE a command runs, stop it AT THE END.
  * ``start()`` / ``stop()`` : daemon mode for Claude Code hooks (background music).

Guiding principle (see DESIGN.md):
    PRESENCE of sound = "working"; ABSENCE of sound = "done, come back".
Silence is the signal.
"""

from __future__ import annotations

import errno
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

import numpy as np

from . import bank, favorites
from .player import play_loop, play_loop_variation, to_pcm16
from .sequencer import build_track


# PID file for daemon mode (a single background track at a time).
# Fall back to /tmp when XDG_RUNTIME_DIR points to another user's session and
# is not writable -- this happens when a non-graphical user borrows a real
# user's PipeWire socket.
_RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp")
_PIDFILE = (
    (_RUNTIME / "purrd.pid")
    if os.access(_RUNTIME, os.W_OK)
    else Path("/tmp") / f"purrd-{os.getuid()}.pid"
)


def _render(bpm: int, seconds: int, seed: int, style: str, volume: float) -> bytes:
    return to_pcm16(build_track(seconds=seconds, bpm=bpm, seed=seed, style=style, volume=volume))


def _scale_pcm(pcm: bytes, volume: float) -> bytes:
    """Scale s16le mono PCM by ``volume``, mirroring the synth path's gain."""
    if not pcm:
        return b""
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float64) * volume
    return np.clip(samples, -32768.0, 32767.0).astype("<i2").tobytes()


def _resolve(
    bpm: int, seconds: int, seed: int | None, style: str | None, use_favorites: bool
) -> tuple[int, int, int, str]:
    """Resolve parameters, preferring explicit seed/style over favorites over default."""
    return favorites.resolve_params(bpm, seconds, seed, style=style, use_favorites=use_favorites)


def _next_pcm(
    bpm: int | None,
    seconds: int | None,
    seed: int | None,
    style: str | None,
    use_favorites: bool,
    volume: float,
) -> bytes:
    """Choose the next track: a bank file when the weighted draw wins, else synth.

    At ratio 0.0 (or an empty bank) this is a strict non-regression: it resolves
    and renders exactly as the synth path always has.
    """
    path = bank.pick_track(bank.bank_ratio())
    if path is not None:
        pcm = bank.decode_pcm(path)
        if pcm:
            return _scale_pcm(pcm, volume)
    rbpm, rseconds, rseed, rstyle = _resolve(bpm, seconds, seed, style, use_favorites)
    return _render(rbpm, rseconds, rseed, rstyle, volume)


def run_with_music(
    cmd: list[str],
    bpm: int | None = None,
    seconds: int | None = None,
    seed: int | None = None,
    volume: float = 1.0,
    style: str | None = None,
    use_favorites: bool = True,
    auto_variation: bool = False,
) -> int:
    """Run ``cmd``, play music in the background, stop it as soon as the command ends.

    If ``seed`` is ``None`` and ``use_favorites`` is ``True``, a random saved
    favorite is picked when available; otherwise the default seed is used.

    When ``auto_variation`` is ``True`` and ``seed`` is not explicit, the music
    picks a new random favorite every time the track ends, so long sessions stay
    fresh.

    Returns the command's exit code.
    """
    stop = threading.Event()
    thread: threading.Thread

    if auto_variation and seed is None:

        def _make_pcm() -> bytes:
            return _next_pcm(bpm, seconds, None, style, use_favorites, volume)

        thread = threading.Thread(target=play_loop_variation, args=(_make_pcm, stop), daemon=True)
    else:
        pcm = _next_pcm(bpm, seconds, seed, style, use_favorites, volume)
        thread = threading.Thread(target=play_loop, args=(pcm, stop), daemon=True)

    thread.start()
    try:
        return subprocess.run(cmd).returncode
    finally:
        stop.set()
        # Give the player thread a reasonable but bounded window to drain
        # and terminate the underlying audio subprocess cleanly. The real
        # guarantee comes from the SIGTERM/SIGKILL sequence in player.py.
        thread.join(timeout=5.0)


def is_running() -> bool:
    """Is there already an active background track?"""
    try:
        pid = int(_PIDFILE.read_text())
        os.kill(pid, 0)
        return True
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        return False


def _wait_until_stopped(timeout: float = 5.0) -> None:
    """Wait until no daemon is tracked or until ``timeout`` expires."""
    deadline = time.monotonic() + timeout
    while is_running() and time.monotonic() < deadline:
        time.sleep(0.05)


def _alive(pid: int) -> bool:
    """Is ``pid`` still a live process (a zombie counts as gone)?"""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        # /proc/<pid>/stat: "pid (comm) S ..." -- the state follows the last ")".
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return True
    return state != "Z"


def _wait_gone(pid: int, timeout: float) -> bool:
    """Poll until ``pid`` is gone; ``True`` if it went away before ``timeout``."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.05)
    return not _alive(pid)


def _release_pidfile(pid: int) -> None:
    """Remove the PID file only if it still names ``pid``.

    The file is shared by every daemon that ever ran. When ``start()`` replaces
    a daemon, the old one may die slowly (its audio pipe drains first) and its
    cleanup used to erase the file unconditionally -- after the newcomer had
    already registered. The newcomer then had no entry: ``stop()`` found
    nothing to kill, ``start()`` forked yet another daemon, and the orphan
    played for hours. Only the owner of the entry may remove it.
    """
    try:
        if int(_PIDFILE.read_text()) != pid:
            return
    except (FileNotFoundError, ValueError):
        return
    _PIDFILE.unlink(missing_ok=True)


def start(
    bpm: int | None = None,
    seconds: int | None = None,
    seed: int | None = None,
    volume: float = 1.0,
    style: str | None = None,
    use_favorites: bool = True,
    auto_variation: bool = False,
) -> None:
    """Start the music as a detached background process (for hooks). Idempotent.

    The parent returns immediately: a hook must never block Claude.

    When ``auto_variation`` is ``True`` and ``seed`` is not explicit, the daemon
    picks a new random favorite every time the track ends instead of looping the
    same one forever.
    """
    # If an old daemon is still around, replace it with a fresh one. This
    # prevents a stale daemon from surviving when Claude Code is restarted.
    if is_running():
        stop()
        # Make sure the old daemon really terminated before we reuse the PID
        # file. Without this, the new child could overwrite a PID still owned
        # by the dying old daemon.
        _wait_until_stopped(timeout=3.0)
        if is_running():
            # The old daemon would not die: overwriting its entry would orphan
            # it (music playing with nothing able to stop it). It is still
            # playing, which is what the caller wanted -- leave it alone.
            return

    # Resolve once for the parent; the child will re-resolve if needed.
    rbpm, rseconds, rseed, rstyle = _resolve(bpm, seconds, seed, style, use_favorites)

    pid = os.fork()
    if pid > 0:  # parent: return immediately
        # Give the child a short moment to write the PID file so that a
        # status/start check right after this call is accurate.
        deadline = time.monotonic() + 1.0
        while not _PIDFILE.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        return

    # --- child: detach and play until it receives SIGTERM ---
    os.setsid()
    try:
        _PIDFILE.write_text(str(os.getpid()))
    except OSError as exc:
        # If we cannot write the PID file there is no point staying alive.
        if exc.errno != errno.EEXIST:
            os._exit(1)

    _stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: _stop.set())
    try:
        if auto_variation and seed is None:

            def _make_pcm() -> bytes:
                return _next_pcm(bpm, seconds, None, style, use_favorites, volume)

            play_loop_variation(_make_pcm, _stop)
        else:
            play_loop(_next_pcm(bpm, seconds, seed, style, use_favorites, volume), _stop)
    finally:
        # Only our own entry: a newer daemon may have registered meanwhile.
        _release_pidfile(os.getpid())
    os._exit(0)


def stop() -> None:
    """Stop the background music (no-op if nothing is playing)."""
    try:
        pid = int(_PIDFILE.read_text())
    except (FileNotFoundError, ValueError):
        return

    # Try the process group first (covers the daemon + its audio subprocess).
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(os.getpgid(pid), sig)
        except PermissionError:
            # Another user's process; we cannot kill it, but we can still unlink
            # the stale PID file below.
            break
        except ProcessLookupError:
            # Process already gone.
            break
        # Give the process group a real chance to die (the audio pipe drains
        # first) before escalating; returning while it is still dying is how
        # the next ``start()`` ends up racing it for the PID file.
        if _wait_gone(pid, timeout=2.0):
            break

    _release_pidfile(pid)
