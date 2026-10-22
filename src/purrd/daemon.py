"""Client/server daemon so `purrd` can be used from users without direct audio access.

The daemon runs under a user/session that *does* have audio (e.g. your desktop user on a
Wayland desktop, or a Docker container with `--device /dev/snd`). Other users
(or containers) send commands to it over a Unix domain socket.

Supported commands (JSON one-liner over the socket):

* ``{"cmd": "start", ...}``  - start background music.
* ``{"cmd": "stop"}``          - stop background music.
* ``{"cmd": "stop-voice"}``   - interrupt any voice sample.
* ``{"cmd": "say", "event": "done"}`` - play a voice event.
* ``{"cmd": "status"}``       - return whether music is currently running.

Environment variables:

* ``PURRD_DAEMON_SOCK`` - path to the Unix socket. Defaults to
  ``$PURRD_CONFIG_DIR/run/purrd.sock``, then ``$XDG_RUNTIME_DIR/purrd/purrd.sock``,
  then ``~/.local/state/purrd/run/purrd.sock``.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import threading
from pathlib import Path
from typing import Any

from . import runner, voice


def _default_socket_dir() -> Path:
    """Return the directory that hosts the default daemon socket."""
    config_dir = os.environ.get("PURRD_CONFIG_DIR")
    if config_dir:
        return Path(config_dir) / "run"
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir) / "purrd"
    return Path.home() / ".local" / "state" / "purrd" / "run"


# Default socket location. The shared-directory setup used by the isolated
# `coder` user is now configured at runtime via PURRD_CONFIG_DIR instead of being
# hard-coded.
_DEFAULT_SOCK = _default_socket_dir() / "purrd.sock"


def socket_path() -> Path:
    """Return the active daemon socket path."""
    env_sock = os.environ.get("PURRD_DAEMON_SOCK")
    if env_sock:
        return Path(env_sock)
    return _DEFAULT_SOCK


def _ensure_socket_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


class Daemon:
    """Unix-socket daemon that executes purrd audio commands in the real session."""

    def __init__(self, sock: Path | None = None) -> None:
        self.sock = sock or socket_path()
        self._lock = threading.Lock()
        self._running = False

    def run(self) -> None:
        """Start listening and dispatch commands until SIGTERM."""
        _ensure_socket_dir(self.sock)
        if self.sock.exists():
            self.sock.unlink()

        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(str(self.sock))
        s.listen(8)
        # Group-writable so any member of devshare can submit commands.
        os.chmod(self.sock, 0o660)

        self._running = True
        # Signal handlers only work in the main interpreter thread. When the
        # daemon is driven by a test thread we rely on the socket closure for
        # shutdown instead.
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, lambda *_: self._shutdown(s))
            signal.signal(signal.SIGINT, lambda *_: self._shutdown(s))

        try:
            while self._running:
                try:
                    conn, _ = s.accept()
                except OSError:
                    break
                threading.Thread(target=self._handle, args=(conn,), daemon=True).start()
        finally:
            s.close()
            self.sock.unlink(missing_ok=True)

    def _shutdown(self, s: socket.socket) -> None:
        self._running = False
        try:
            s.close()
        except OSError:
            pass

    def _handle(self, conn: socket.socket) -> None:
        with conn:
            try:
                data = b""
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                    if len(data) > 65536:
                        raise ValueError("Request too large")
                if not data:
                    return
                msg = json.loads(data.decode())
                result = self._dispatch(msg)
                conn.sendall(json.dumps({"status": "ok", "result": result}).encode())
            except Exception as exc:  # noqa: BLE001
                try:
                    conn.sendall(json.dumps({"status": "error", "message": str(exc)}).encode())
                except OSError:
                    pass

    def _dispatch(self, msg: dict[str, Any]) -> Any:
        cmd = msg.get("cmd")
        if cmd == "start":
            runner.start(
                bpm=msg.get("bpm"),
                seconds=msg.get("seconds"),
                seed=msg.get("seed"),
                volume=msg.get("volume", 1.0),
                style=msg.get("style"),
                use_favorites=msg.get("use_favorites", True),
                auto_variation=msg.get("auto_variation", False),
            )
            return None
        if cmd == "stop":
            runner.stop()
            return None
        if cmd == "stop-voice":
            voice.stop_voice()
            return None
        if cmd == "say":
            event = msg.get("event")
            if event not in voice.EVENTS:
                raise ValueError(f"Unknown event {event!r}")
            voice.play_event(event)
            return None
        if cmd == "status":
            return runner.is_running()
        raise ValueError(f"Unknown command {cmd!r}")


def daemon_available() -> bool:
    """Is there a daemon socket we can use?"""
    path = socket_path()
    return path.exists() and os.access(str(path), os.W_OK)


def send_command(msg: dict[str, Any]) -> dict[str, Any]:
    """Send a JSON command to the daemon without blocking for a response.

    The daemon executes commands asynchronously; callers (Claude Code hooks)
    must return immediately so the agent is never slowed down (FR-2).
    """
    path = socket_path()
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(str(path))
        s.sendall(json.dumps(msg).encode())
        s.shutdown(socket.SHUT_WR)
        return {"status": "ok"}
    finally:
        s.close()


def run_daemon() -> None:
    """Entry point used by ``purrd daemon``."""
    Daemon().run()
