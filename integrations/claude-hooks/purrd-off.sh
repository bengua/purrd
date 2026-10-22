#!/usr/bin/env bash
# Claude Code hook: stop the background music, stop any voice sample, and announce the event.
# Usage: purrd-off.sh [done|permission]

PURRD="${PURRD:-purrd}"
export PURRD_CONFIG_DIR="${PURRD_CONFIG_DIR:-}"
export PURRD_DAEMON_SOCK="${PURRD_DAEMON_SOCK:-}"

event=${1:-done}
"$PURRD" stop
"$PURRD" stop-voice
"$PURRD" say "$event"
