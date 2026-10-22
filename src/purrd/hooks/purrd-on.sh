#!/usr/bin/env bash
# Claude Code hook: announce the start of work and begin the background music.
#
# ``purrd`` itself now ensures XDG_RUNTIME_DIR / DBUS_SESSION_BUS_ADDRESS are
# set, so this hook only needs to call the binary. Override PURRD if the binary
# is not on PATH.
# Add `--auto-variation` to rotate through favorites on long sessions.
PURRD="${PURRD:-purrd}"

"$PURRD" say start
# Only start the music if it is not already running. This keeps the groove
# alive across permission prompts without restarting the track every prompt.
if ! "$PURRD" status >/dev/null 2>&1; then
    nice -n 19 "$PURRD" start
fi
