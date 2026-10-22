"""Filesystem locations shared across the package."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "purrd"


def config_dir() -> Path:
    """Return the user configuration directory.

    Resolution order:

    1. ``PURRD_CONFIG_DIR`` environment variable, if set to a non-empty value.
    2. ``XDG_CONFIG_HOME/purrd`` as fallback.
    3. ``~/.config/purrd`` as final fallback.
    """
    base = os.environ.get("PURRD_CONFIG_DIR")
    if base:
        return Path(base)
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / ".config" / APP_NAME


def data_dir() -> Path:
    """Return the user data directory, respecting ``XDG_DATA_HOME``."""
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


def packs_dir() -> Path:
    """Return the directory holding CESP voice packs.

    Resolution order:

    1. ``PURRD_PACKS_DIR`` environment variable, if set to a non-empty value.
    2. ``XDG_DATA_HOME/purrd/packs`` as fallback.
    """
    base = os.environ.get("PURRD_PACKS_DIR")
    if base:
        return Path(base)
    return data_dir() / "packs"


def bank_dir() -> Path:
    """Return the directory holding pre-generated ambience tracks.

    Resolution order:

    1. ``PURRD_BANK_DIR`` environment variable, if set to a non-empty value.
    2. ``XDG_DATA_HOME/purrd/bank`` as fallback.

    The directory is never created; its absence is a valid state (synth-only).
    """
    base = os.environ.get("PURRD_BANK_DIR")
    if base:
        return Path(base)
    return data_dir() / "bank"


def migrate_legacy_packs() -> None:
    """Move legacy ``~/.purrd/packs`` to the XDG data directory once.

    The migration runs only when ``PURRD_PACKS_DIR`` is unset or empty, the
    legacy directory exists, and the XDG target does not.  If both locations
    exist, a discrete message is printed to stderr because no automatic merge
    is done.
    """
    if os.environ.get("PURRD_PACKS_DIR"):
        return

    legacy = Path.home() / ".purrd" / "packs"
    if not legacy.exists():
        return

    target = packs_dir()
    if target.exists():
        print(
            f"Legacy packs left in {legacy}; current location is {target}. "
            "No automatic merge was performed.",
            file=sys.stderr,
        )
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy), str(target))
    print(f"Migrated packs from {legacy} to {target}.", file=sys.stderr)
