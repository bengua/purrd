#!/usr/bin/env bash
# Install purrd Claude Code hooks into the user's home.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PURRD_BIN="${1:-${REPO_ROOT}/.venv/bin/purrd}"

if [ ! -x "$PURRD_BIN" ]; then
    echo "purrd binary not found: $PURRD_BIN" >&2
    echo "Usage: $0 [path/to/purrd]" >&2
    exit 1
fi

HOOK_DIR="$HOME/.purrd/hooks"
mkdir -p "$HOOK_DIR"

install_hook() {
    local name="$1"
    local dest="$HOOK_DIR/$name"
    sed -e "s|PURRD=\"\${PURRD:-purrd}\"|PURRD=\"${PURRD_BIN}\"|" \
        "$REPO_ROOT/src/purrd/hooks/$name" > "$dest"
    chmod +x "$dest"
    echo "installed $dest"
}

install_hook purrd-on.sh
install_hook purrd-off.sh

echo
echo "Add this to ~/.claude/settings.json:"
cat <<'EOF'
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "~/.purrd/hooks/purrd-on.sh", "async": true } ] }
    ],
    "Stop": [
      { "hooks": [ { "type": "command", "command": "~/.purrd/hooks/purrd-off.sh done" } ] }
    ],
    "SessionEnd": [
      { "hooks": [ { "type": "command", "command": "~/.purrd/hooks/purrd-off.sh done" } ] }
    ],
    "Notification": [
      { "hooks": [ { "type": "command", "command": "~/.purrd/hooks/purrd-off.sh permission" } ] }
    ]
  }
}
EOF
