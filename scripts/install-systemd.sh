#!/usr/bin/env bash
# Install the systemd user service for the purrd daemon.
# Run this as the user that owns the audio session (usually your desktop user).

set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="${HOME}/.config/systemd/user"

mkdir -p "$TARGET_DIR"
cp "$SOURCE_DIR/purrd-daemon.service" "$TARGET_DIR/"

systemctl --user daemon-reload
systemctl --user enable purrd-daemon.service
systemctl --user start purrd-daemon.service

echo "purrd-daemon user service installed and started."
echo "Check status: systemctl --user status purrd-daemon"
