#!/usr/bin/env bash
# Claude Code hook: announce the start of work and begin the background music.
#
# Set PURRD_DAEMON_SOCK to route commands through a shared daemon (useful for
# isolated users or Docker containers). When unset, purrd runs in local mode.

PURRD="${PURRD:-purrd}"
export PURRD_CONFIG_DIR="${PURRD_CONFIG_DIR:-}"
export PURRD_DAEMON_SOCK="${PURRD_DAEMON_SOCK:-}"

"$PURRD" say start
nice -n 19 "$PURRD" start
