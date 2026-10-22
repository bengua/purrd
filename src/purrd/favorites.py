"""Favorites persistence for purrd's studio curator.

Stores kept loops as deterministic parameters (seed, bpm, seconds) in
``~/.config/purrd/favorites.toml``. The actual audio files are never persisted;
they can always be regenerated from these parameters.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from purrd import _paths
from purrd import _toml as tomllib

MANIFEST_NAME = "favorites.toml"

#: Default fallback when no favorites exist and no seed is explicit.
DEFAULT_FAVORITE: dict[str, Any] = {"seed": 0, "bpm": 86, "seconds": 32}


def manifest_path() -> Path:
    """Path to ``favorites.toml``."""
    return _paths.config_dir() / MANIFEST_NAME


def load() -> list[dict[str, Any]]:
    """Load favorites from disk. Returns an empty list if none exist."""
    path = manifest_path()
    if not path.exists():
        return []
    try:
        data = tomllib.load(path)
    except (OSError, ValueError):
        return []
    entries = data.get("favorite", [])
    if isinstance(entries, dict):
        return [entries]
    return [dict(entry) for entry in entries if isinstance(entry, dict)]


def save(entries: list[dict[str, Any]]) -> None:
    """Write favorites to disk, creating the config directory if needed."""
    path = manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# purrd favorite loops — deterministic parameters only.\n"]
    lines.append("# Regenerate the audio with: purrd --seed <seed> --bpm <bpm> --style <style>\n")
    lines.append("\n")
    for entry in entries:
        lines.append("[[favorite]]\n")
        for key in ("seed", "bpm", "seconds", "style"):
            value = entry.get(key)
            if value is not None:
                if isinstance(value, str):
                    lines.append(f'{key} = "{value}"\n')
                else:
                    lines.append(f"{key} = {value}\n")
        lines.append("\n")

    path.write_text("".join(lines), encoding="utf-8")


def _candidate(seed: int, bpm: int, seconds: int, style: str | None) -> dict[str, Any]:
    """Build a favorite entry, omitting the style field when it is None/classic."""
    entry: dict[str, Any] = {
        "seed": int(seed),
        "bpm": int(bpm),
        "seconds": int(seconds),
    }
    if style is not None and style != "classic":
        entry["style"] = style
    return entry


def add(seed: int, bpm: int, seconds: int, style: str | None = None) -> None:
    """Add a new favorite, avoiding exact duplicates."""
    entries = load()
    candidate = _candidate(seed, bpm, seconds, style)
    if candidate not in entries:
        entries.append(candidate)
        save(entries)


def remove(seed: int, bpm: int, seconds: int, style: str | None = None) -> None:
    """Remove the matching favorite, if it exists.

    The match intentionally ignores the ``style`` field by default so that
    removing an entry the user sees in the UI works even if that entry has a
    style stored. Passing ``style`` makes the match strict.
    """
    candidate = _candidate(seed, bpm, seconds, style)
    if style is None:
        entries = [
            e
            for e in load()
            if not (
                e.get("seed") == candidate["seed"]
                and e.get("bpm") == candidate["bpm"]
                and e.get("seconds") == candidate["seconds"]
            )
        ]
    else:
        entries = [e for e in load() if e != candidate]
    save(entries)


def pick_random(rng: random.Random | None = None) -> dict[str, Any] | None:
    """Pick a random favorite, or ``None`` if the list is empty."""
    entries = load()
    if not entries:
        return None
    if rng is None:
        rng = random.Random()
    return dict(rng.choice(entries))


def generate_presets(
    count: int = 10,
    bpm_min: int = 78,
    bpm_max: int = 92,
    seconds: int = 32,
    rng: np.random.Generator | None = None,
    style_pool: tuple[str, ...] | list[str] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Generate ``count`` distinct deterministic presets with varied tempos.

    Args:
        style_pool: If given, each preset includes a randomly drawn ``style``
            from this pool. If ``None``, no style field is written and the
            preset will fall back to ``"classic"`` at playback time.
        progress: Optional callback invoked as ``progress(done, total)`` after
            each successful preset.
    """
    if rng is None:
        rng = np.random.default_rng()
    presets: list[dict[str, Any]] = []
    seeds = set()
    style_pool_tuple = tuple(style_pool) if style_pool else ()
    while len(presets) < count:
        seed = int(rng.integers(0, 2**31))
        if seed in seeds:
            continue
        seeds.add(seed)
        bpm = int(rng.integers(bpm_min, bpm_max + 1))
        preset: dict[str, Any] = {"seed": seed, "bpm": bpm, "seconds": seconds}
        if style_pool_tuple:
            preset["style"] = str(rng.choice(style_pool_tuple))
        presets.append(preset)
        if progress is not None:
            progress(len(presets), count)
    return presets


def resolve_params(
    bpm: int | None,
    seconds: int | None,
    seed: int | None,
    style: str | None = None,
    use_favorites: bool = True,
) -> tuple[int, int, int, str]:
    """Resolve playback parameters with per-field explicit > favorite > default priority.

    Each field is resolved independently:
        - Explicit value wins over the favorite's value and the default.
        - A favorite is consulted only when ``seed`` is not explicit.
        - Missing ``style`` (explicit or in favorite) resolves to ``"classic"``.

    Returns:
        ``(bpm, seconds, seed, style)`` ready to pass to the sequencer.
    """
    resolved_bpm = int(DEFAULT_FAVORITE["bpm"])
    resolved_seconds = int(DEFAULT_FAVORITE["seconds"])
    resolved_seed = int(DEFAULT_FAVORITE["seed"])
    resolved_style: str = "classic"
    favorite_style: str | None = None

    if seed is None and use_favorites:
        fav = pick_random()
        if fav is not None:
            resolved_bpm = int(fav["bpm"])
            resolved_seconds = int(fav["seconds"])
            resolved_seed = int(fav["seed"])
            favorite_style = fav.get("style")

    if bpm is not None:
        resolved_bpm = int(bpm)
    if seconds is not None:
        resolved_seconds = int(seconds)
    if seed is not None:
        resolved_seed = int(seed)

    if style is not None:
        resolved_style = style
    elif isinstance(favorite_style, str):
        resolved_style = favorite_style

    return resolved_bpm, resolved_seconds, resolved_seed, resolved_style
