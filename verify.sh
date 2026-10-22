#!/usr/bin/env bash
# Local check before pushing: the same lint and tests the CI runs.
# Uses uv when available, otherwise the current Python environment
# (install it first with `pip install -e ".[dev]"`).
# No sound card needed: the tests never open a real audio device.
set -euo pipefail
cd "$(dirname "$0")"

if command -v uv >/dev/null; then
  uv sync --extra dev -q
  run() { uv run "$@"; }
else
  run() { "$@"; }
fi

run ruff check .
run pytest -q
echo "OK"
