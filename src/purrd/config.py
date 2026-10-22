"""User configuration persistence for purrd."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from purrd import _paths
from purrd import _toml as tomllib


MANIFEST_NAME = "config.toml"


def config_path() -> Path:
    """Path to ``~/.config/purrd/config.toml``."""
    return _paths.config_dir() / MANIFEST_NAME


def load() -> dict[str, Any]:
    """Load configuration from disk. Returns an empty dict if none exists."""
    path = config_path()
    if not path.exists():
        return {}
    try:
        return tomllib.load(path)
    except (OSError, ValueError):
        return {}


def save(cfg: dict[str, Any]) -> None:
    """Write configuration to disk, creating the config directory if needed."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# purrd user configuration.\n\n"]

    for section, values in cfg.items():
        if not isinstance(values, dict):
            continue
        lines.append(f"[{section}]\n")
        for key, value in values.items():
            if isinstance(value, str):
                lines.append(f'{key} = "{value}"\n')
            elif isinstance(value, bool):
                lines.append(f"{key} = {str(value).lower()}\n")
            elif isinstance(value, (int, float)):
                lines.append(f"{key} = {value}\n")
            else:
                lines.append(f'{key} = "{value}"\n')
        lines.append("\n")

    path.write_text("".join(lines), encoding="utf-8")
