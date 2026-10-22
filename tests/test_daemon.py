"""Tests for the client/server daemon layer."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from pathlib import Path

import pytest

from purrd import daemon


def _wait_for_socket(sock: Path, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if sock.exists():
            return
        time.sleep(0.01)
    raise FileNotFoundError(f"Socket did not appear in time: {sock}")


def _send(sock: Path, msg: dict) -> dict:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(str(sock))
        s.sendall(json.dumps(msg).encode())
        s.shutdown(socket.SHUT_WR)
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
        return json.loads(data.decode()) if data else {}
    finally:
        s.close()


def test_daemon_available_false_when_no_socket(tmp_path: Path) -> None:
    os.environ["PURRD_DAEMON_SOCK"] = str(tmp_path / "missing.sock")
    assert not daemon.daemon_available()


def test_daemon_status_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sock = tmp_path / "purrd.sock"
    os.environ["PURRD_DAEMON_SOCK"] = str(sock)

    calls = []
    monkeypatch.setattr(daemon.runner, "is_running", lambda: calls.append("status") or True)

    d = daemon.Daemon(sock)
    t = threading.Thread(target=d.run, daemon=True)
    t.start()
    try:
        _wait_for_socket(sock)
        resp = _send(sock, {"cmd": "status"})
    finally:
        d._running = False
        if sock.exists():
            sock.unlink(missing_ok=True)
    t.join(timeout=2)

    assert resp == {"status": "ok", "result": True}
    assert calls == ["status"]


def test_daemon_stop_and_stop_voice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sock = tmp_path / "purrd.sock"
    os.environ["PURRD_DAEMON_SOCK"] = str(sock)

    calls = []
    monkeypatch.setattr(daemon.runner, "stop", lambda: calls.append("stop"))
    monkeypatch.setattr(daemon.voice, "stop_voice", lambda: calls.append("stop-voice"))

    d = daemon.Daemon(sock)
    t = threading.Thread(target=d.run, daemon=True)
    t.start()
    try:
        _wait_for_socket(sock)
        _send(sock, {"cmd": "stop"})
        _send(sock, {"cmd": "stop-voice"})
    finally:
        d._running = False
        if sock.exists():
            sock.unlink(missing_ok=True)
    t.join(timeout=2)

    assert calls == ["stop", "stop-voice"]


def test_daemon_say_known_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sock = tmp_path / "purrd.sock"
    os.environ["PURRD_DAEMON_SOCK"] = str(sock)

    calls = []
    monkeypatch.setattr(daemon.voice, "play_event", lambda event: calls.append(event))

    d = daemon.Daemon(sock)
    t = threading.Thread(target=d.run, daemon=True)
    t.start()
    try:
        _wait_for_socket(sock)
        resp = _send(sock, {"cmd": "say", "event": "done"})
    finally:
        d._running = False
        if sock.exists():
            sock.unlink(missing_ok=True)
    t.join(timeout=2)

    assert resp == {"status": "ok", "result": None}
    assert calls == ["done"]


def test_daemon_say_unknown_event_returns_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sock = tmp_path / "purrd.sock"
    os.environ["PURRD_DAEMON_SOCK"] = str(sock)

    monkeypatch.setattr(daemon.voice, "play_event", lambda event: None)

    d = daemon.Daemon(sock)
    t = threading.Thread(target=d.run, daemon=True)
    t.start()
    try:
        _wait_for_socket(sock)
        resp = _send(sock, {"cmd": "say", "event": "bogus"})
    finally:
        d._running = False
        if sock.exists():
            sock.unlink(missing_ok=True)
    t.join(timeout=2)

    assert resp["status"] == "error"
    assert "Unknown event" in resp["message"]


def test_daemon_start_forwards_parameters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sock = tmp_path / "purrd.sock"
    os.environ["PURRD_DAEMON_SOCK"] = str(sock)

    calls = []
    monkeypatch.setattr(daemon.runner, "start", lambda **kw: calls.append(kw))

    d = daemon.Daemon(sock)
    t = threading.Thread(target=d.run, daemon=True)
    t.start()
    try:
        _wait_for_socket(sock)
        _send(
            sock,
            {
                "cmd": "start",
                "bpm": 90,
                "seconds": 64,
                "seed": 7,
                "volume": 0.5,
                "style": "chill",
                "use_favorites": False,
            },
        )
    finally:
        d._running = False
        if sock.exists():
            sock.unlink(missing_ok=True)
    t.join(timeout=2)

    assert calls == [
        {
            "bpm": 90,
            "seconds": 64,
            "seed": 7,
            "volume": 0.5,
            "style": "chill",
            "use_favorites": False,
            "auto_variation": False,
        }
    ]
