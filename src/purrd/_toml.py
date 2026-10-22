"""Minimal TOML parser for purrd's simple manifests.

Supports only the subset used by purrd:
- Comments starting with ``#``
- Sections: ``[section]``
- Array-of-tables: ``[[array]]``
- Inline strings with double quotes
- Integers, floats, booleans

This avoids adding ``tomli`` or requiring Python >= 3.11.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _unescape(value: str) -> str:
    """Handle a few common escapes inside double-quoted strings."""
    return value.replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\").replace('\\"', '"')


def _parse_value(raw: str) -> Any:
    """Parse a TOML scalar value."""
    value = raw.strip()
    if value.startswith('"') and value.endswith('"'):
        return _unescape(value[1:-1])
    if value == "true":
        return True
    if value == "false":
        return False
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Unsupported TOML value: {value!r}") from exc


def _split_line(line: str) -> tuple[str, Any]:
    """Split ``key = value`` into a key and parsed value."""
    key, _, rest = line.partition("=")
    return key.strip(), _parse_value(rest)


def load(path: Path) -> dict[str, Any]:
    """Parse a minimal TOML file into a nested dict.

    Array-of-tables are returned as a list of dicts under the table name.
    """
    data: dict[str, Any] = {}
    current_table: str | None = None
    current_entry: dict[str, Any] | None = None

    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("[[") and line.endswith("]]"):
                table = line[2:-2].strip()
                current_table = table
                current_entry = {}
                data.setdefault(table, []).append(current_entry)
                continue

            if line.startswith("[") and line.endswith("]"):
                table = line[1:-1].strip()
                current_table = table
                current_entry = None
                data.setdefault(table, {})
                continue

            key, value = _split_line(line)

            if current_entry is not None and current_table is not None:
                current_entry[key] = value
            elif current_table is not None:
                table_data = data.setdefault(current_table, {})
                if isinstance(table_data, dict):
                    table_data[key] = value

    return data
