"""The PID file has exactly one owner at a time.

Regression for the orphan daemon: an old daemon dying slowly erased the PID
file of the daemon that had just replaced it, so nothing could ever stop the
newcomer and the music played for hours.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from purrd import runner


@pytest.fixture
def pidfile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "purrd.pid"
    monkeypatch.setattr(runner, "_PIDFILE", path)
    return path


def test_release_removes_own_entry(pidfile: Path) -> None:
    pidfile.write_text("4242")
    runner._release_pidfile(4242)
    assert not pidfile.exists()


def test_release_keeps_a_newer_daemon_entry(pidfile: Path) -> None:
    pidfile.write_text("4243")
    runner._release_pidfile(4242)
    assert pidfile.read_text() == "4243"


def test_release_without_file_is_a_noop(pidfile: Path) -> None:
    runner._release_pidfile(4242)
    assert not pidfile.exists()


def test_release_ignores_garbage(pidfile: Path) -> None:
    pidfile.write_text("not a pid")
    runner._release_pidfile(4242)
    assert pidfile.exists()


def test_stop_kills_the_tracked_group_and_releases(pidfile: Path) -> None:
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True
    )
    try:
        pidfile.write_text(str(proc.pid))
        runner.stop()
        assert proc.wait(timeout=5) < 0  # killed by a signal
        assert not pidfile.exists()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_stop_without_file_is_a_noop(pidfile: Path) -> None:
    runner.stop()
    assert not pidfile.exists()


def test_alive_treats_a_zombie_as_gone() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    try:
        assert runner._wait_gone(proc.pid, timeout=5.0)
    finally:
        proc.wait()


def test_start_does_not_fork_over_a_daemon_that_will_not_die(
    pidfile: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pidfile.write_text(str(os.getpid()))  # a live process that stop() is told to ignore
    monkeypatch.setattr(runner, "stop", lambda: None)
    monkeypatch.setattr(runner, "_wait_until_stopped", lambda timeout: None)

    def forbidden_fork() -> int:
        raise AssertionError("start() must not fork while another daemon owns the PID file")

    monkeypatch.setattr(runner.os, "fork", forbidden_fork)
    runner.start()
    assert pidfile.read_text() == str(os.getpid())
