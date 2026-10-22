"""The player's stop sequence: terminate, then kill only if it lingers, and
never raise even when the process object misbehaves. No real audio."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

from purrd import player


def _proc(wait_side_effect):
    p = MagicMock()
    p.stdin = MagicMock()
    p.wait.side_effect = wait_side_effect
    return p


def test_terminate_then_no_kill_when_it_exits():
    # wait() returns cleanly on the first (terminate) call -> no kill.
    p = _proc([0])
    player._terminate_player(p, term_timeout=0.01, kill_timeout=0.01)
    p.terminate.assert_called_once()
    p.kill.assert_not_called()
    p.stdin.close.assert_called_once()


def test_kill_when_terminate_does_not_stop_it():
    # First wait (after terminate) times out, second wait (after kill) returns.
    p = _proc([subprocess.TimeoutExpired(cmd="x", timeout=0.01), 0])
    player._terminate_player(p, term_timeout=0.01, kill_timeout=0.01)
    p.terminate.assert_called_once()
    p.kill.assert_called_once()


def test_stop_never_raises_when_the_process_misbehaves():
    # terminate/kill/wait/close all blow up: the sequence must swallow it.
    p = MagicMock()
    p.stdin.close.side_effect = OSError("closed")
    p.terminate.side_effect = OSError("gone")
    p.kill.side_effect = OSError("gone")
    p.wait.side_effect = subprocess.TimeoutExpired(cmd="x", timeout=0.01)
    player._terminate_player(p, term_timeout=0.01, kill_timeout=0.01)  # no raise
