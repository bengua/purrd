#!/usr/bin/env bash
# Generic wrapper: play purrd in the background during any long command, at low
# priority (nice) so it never steals CPU from the task.
#
# Install it as a shell function in your ~/.bashrc:
#     withsound() { nice -n 19 purrd "$@"; }
#
# Then:  withsound make -j8     /     withsound cargo build
nice -n 19 purrd "$@"
