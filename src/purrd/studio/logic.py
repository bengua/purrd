"""Widget-free business logic for the purrd studio GUI.

Everything here is pure Python / filesystem logic and can be unit-tested without
GTK, a display, or a sound card.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from purrd import cesp, favorites
from purrd.sequencer import build_track

VOICE_EVENTS = ("start", "done", "permission", "error")


def repo_root() -> Path:
    """Return the repository root containing ``scripts/``."""
    return Path(__file__).resolve().parent.parent.parent.parent


def generate_loop_presets(
    count: int = 10,
    bpm_min: int = 78,
    bpm_max: int = 92,
    seconds: int = 32,
    style_pool: tuple[str, ...] | list[str] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Generate ``count`` distinct loop presets using :mod:`purrd.favorites`.

    Args:
        count: Number of presets to generate.
        bpm_min: Lower bound for random BPM (inclusive).
        bpm_max: Upper bound for random BPM (inclusive).
        seconds: Track length for each preset.
        style_pool: Pool of styles to draw from. ``None`` keeps presets classic.
        progress: Optional callback invoked as ``progress(done, total)``.
    """
    return favorites.generate_presets(
        count=count,
        bpm_min=bpm_min,
        bpm_max=bpm_max,
        seconds=seconds,
        style_pool=style_pool,
        progress=progress,
    )


def preview_loop_params(
    seed: int,
    bpm: int,
    seconds: int,
    volume: float = 1.0,
    style: str | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> bytes:
    """Render a loop to PCM16 bytes for playback."""
    from purrd.player import to_pcm16

    return to_pcm16(
        build_track(
            seconds=seconds,
            bpm=bpm,
            seed=seed,
            volume=volume,
            style=style or "classic",
            progress=progress,
        )
    )


def add_favorite(seed: int, bpm: int, seconds: int, style: str | None = None) -> None:
    """Persist a kept loop as deterministic parameters."""
    favorites.add(seed, bpm, seconds, style=style)


def remove_favorite(seed: int, bpm: int, seconds: int, style: str | None = None) -> None:
    """Remove a favorite by exact parameters."""
    favorites.remove(seed, bpm, seconds, style=style)


def list_favorites() -> list[dict[str, Any]]:
    """Return the persisted favorites list."""
    return favorites.load()


# --- CESP voice-pack wrappers used by the studio GUI ---


def list_installed_packs() -> list[cesp.CespPack]:
    """Return installed CESP packs, sorted by display name."""
    return cesp.list_installed_packs()


def list_template_packs() -> list[cesp.CespPack]:
    """Return available CESP template packs discovered on disk."""
    return cesp.list_template_packs()


def get_active_pack() -> cesp.CespPack | None:
    """Return the currently active CESP pack."""
    return cesp.get_active_pack()


def set_active_pack(name: str) -> None:
    """Persist the active CESP pack name."""
    cesp.set_active_pack(name)


def import_pack(source_dir: Path, *, force: bool = False) -> cesp.CespPack:
    """Import a CESP pack and return it."""
    return cesp.import_pack(source_dir, force=force)


def preview_sound_for_event(event: str) -> Path | None:
    """Return a sound path for the given purrd event from the active pack."""
    pack = cesp.get_active_pack()
    if pack is None:
        return None
    return cesp.random_sound_for_event(pack, event)
