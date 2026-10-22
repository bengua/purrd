#!/usr/bin/env bash
# Claude Code hook: stop the background music and announce the event.
# Usage: purrd-off.sh [done|permission]
PURRD="${PURRD:-purrd}"

event=${1:-done}
# Permission prompts are temporary interruptions: keep the music running so it
# resumes automatically once the user answers.
if [ "$event" != "permission" ]; then
    "$PURRD" stop
fi
"$PURRD" stop-voice
"$PURRD" say "$event"
