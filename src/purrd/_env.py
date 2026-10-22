"""Runtime environment normalization for audio subprocesses.

PipeWire clients (``pw-cat``, ``pactl``) need ``XDG_RUNTIME_DIR`` to locate the
per-user socket.  Claude Code hooks and other minimal environments often strip
this variable, which makes purrd silently fall back to ALSA and fail because the
calling user is not in the ``audio`` group.

This module is imported very early in the CLI so every subprocess launched
afterwards inherits the corrected environment.
"""

from __future__ import annotations

import os


def ensure_audio_env() -> None:
    """Make sure PipeWire/PulseAudio environment variables are set.

    If ``XDG_RUNTIME_DIR`` is missing, default it to ``/run/user/<uid>``.
    If ``DBUS_SESSION_BUS_ADDRESS`` is missing, default it to the bus socket
    under ``XDG_RUNTIME_DIR``.

    Existing values are preserved so users can still override them.
    """
    uid = os.getuid()
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime_dir:
        runtime_dir = f"/run/user/{uid}"
        os.environ["XDG_RUNTIME_DIR"] = runtime_dir

    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={runtime_dir}/bus"


# Normalise once at module load to cover early imports
# (for example the pidfile in :mod:`purrd.runner`).
ensure_audio_env()
