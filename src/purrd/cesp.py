"""CESP voice-pack support for purrd.

A CESP pack is a directory containing an ``openpeon.json`` manifest and a
``sounds/`` subdirectory of audio files.  The manifest maps categories (e.g.
``session.start``, ``task.complete``) to lists of sound entries.

Purrd translates its own events (``start``, ``done``, ``permission``, ``error``)
into CESP categories, picks a sound at random, and plays it over the music.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from purrd import _paths
from purrd.config import load as _load_config, save as _save_config


def bundled_packs_dir() -> Path | None:
    """Return the directory containing packs bundled with the package, if any.

    This works both from a source checkout and from an installed wheel.
    """
    pkg_root = Path(__file__).resolve().parent
    bundled = pkg_root / "data" / "bundled_packs"
    return bundled if bundled.exists() else None


EVENTS = frozenset({"start", "done", "permission", "error"})

#: Mapping from purrd events to CESP categories, in preference order.
EVENT_CATEGORY_MAP: dict[str, tuple[str, ...]] = {
    "start": ("session.start", "task.acknowledge"),
    "done": ("task.complete",),
    "permission": ("input.required",),
    "error": ("task.error",),
}

SR = 44100


@dataclass(frozen=True)
class CespPack:
    """An imported CESP voice pack."""

    pack_dir: Path
    manifest: dict[str, Any]

    @classmethod
    def from_directory(cls, pack_dir: Path) -> CespPack:
        """Load a pack from its directory."""
        manifest = load_manifest(pack_dir / "openpeon.json")
        return cls(pack_dir=pack_dir, manifest=manifest)

    @property
    def name(self) -> str:
        return str(self.manifest.get("name", self.pack_dir.name))

    @property
    def display_name(self) -> str:
        return str(self.manifest.get("display_name", self.name))

    @property
    def language(self) -> str:
        return str(self.manifest.get("language", "en"))

    @property
    def icon(self) -> Path | None:
        icon_name = self.manifest.get("icon")
        if icon_name:
            path = self.pack_dir / icon_name
            if path.exists():
                return path
        return None

    @property
    def categories(self) -> dict[str, dict[str, Any]]:
        return dict(self.manifest.get("categories", {}))


def load_manifest(path: Path) -> dict[str, Any]:
    """Read an ``openpeon.json`` manifest."""
    return json.loads(path.read_text(encoding="utf-8"))


def list_installed_packs(packs_root: Path | None = None) -> list[CespPack]:
    """Return all packs installed under ``~/.purrd/packs``."""
    root = packs_root if packs_root is not None else _paths.packs_dir()
    if not root.exists():
        return []
    packs: list[CespPack] = []
    for entry in root.iterdir():
        manifest = entry / "openpeon.json"
        if not manifest.exists():
            continue
        try:
            packs.append(CespPack.from_directory(entry))
        except (OSError, ValueError):
            continue
    return sorted(packs, key=lambda p: p.display_name.lower())


def category_for_event(event: str) -> tuple[str, ...]:
    """Return candidate CESP categories for a purrd event."""
    if event not in EVENTS:
        raise ValueError(f"Unknown event {event!r}; expected one of: {sorted(EVENTS)}")
    return EVENT_CATEGORY_MAP[event]


def random_sound_for_event(pack: CespPack, event: str) -> Path | None:
    """Pick a random sound file for a purrd event from the given pack.

    Returns ``None`` when the pack has no matching category or the category
    contains no sounds.
    """
    categories = pack.categories
    for category in category_for_event(event):
        entry = categories.get(category, {})
        sounds = entry.get("sounds", []) if isinstance(entry, dict) else []
        if sounds:
            sound = random.choice(sounds)
            return (pack.pack_dir / sound["file"]).resolve()
    return None


def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    """Read a WAV file and return (samples as float64, sample_rate)."""
    with wave.open(str(path), "rb") as w:
        nchannels = w.getnchannels()
        sampwidth = w.getsampwidth()
        framerate = w.getframerate()
        nframes = w.getnframes()
        data = w.readframes(nframes)

    if sampwidth == 1:
        signal = np.frombuffer(data, dtype=np.uint8).astype(np.float64)
        signal = (signal - 128.0) / 128.0
    elif sampwidth == 2:
        signal = np.frombuffer(data, dtype=np.int16).astype(np.float64)
        signal = signal / 32768.0
    else:
        raise RuntimeError(f"Unsupported sample width: {sampwidth}")

    if nchannels == 2:
        signal = signal.reshape(-1, 2).mean(axis=1)
    else:
        signal = signal.reshape(-1)

    return signal, framerate


def _resample_rate(signal: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Linear-resample ``signal`` from ``src_rate`` to ``dst_rate``."""
    if src_rate == dst_rate:
        return signal
    ratio = dst_rate / src_rate
    new_len = max(1, int(len(signal) * ratio))
    old_x = np.arange(len(signal))
    new_x = np.linspace(0, len(signal) - 1, new_len)
    return np.interp(new_x, old_x, signal)


def _decode_with_ffmpeg(src: Path) -> Path:
    """Decode an audio file to a temporary 44.1 kHz mono PCM16 WAV using ffmpeg."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError(f"Cannot decode {src.suffix!r} files without ffmpeg")
    tmp = src.with_suffix(".tmp.wav")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(src),
            "-ar",
            str(SR),
            "-ac",
            "1",
            "-f",
            "wav",
            str(tmp),
        ],
        check=True,
    )
    return tmp


def normalize_audio(src: Path, dst: Path) -> None:
    """Convert any supported audio file to 44.1 kHz / mono / PCM16 WAV."""
    tmp_path: Path | None = None
    try:
        if src.suffix.lower() == ".wav":
            signal, framerate = _read_wav(src)
        else:
            tmp_path = _decode_with_ffmpeg(src)
            signal, framerate = _read_wav(tmp_path)

        if framerate != SR:
            signal = _resample_rate(signal, framerate, SR)

        peak = np.max(np.abs(signal)) or 1.0
        signal = signal / peak * 0.95
        signal = (np.clip(signal, -1.0, 1.0) * 32767).astype(np.int16)

        dst.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(dst), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(signal.tobytes())
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def import_pack(
    source_dir: Path | str,
    packs_root: Path | None = None,
    *,
    force: bool = False,
) -> CespPack:
    """Import a CESP pack into purrd.

    The pack is copied into ``~/.purrd/packs/<name>/`` and all sounds are
    normalized to 44.1 kHz / mono / PCM16 WAV.  The manifest is rewritten so
    sound paths point to the normalized files.
    """
    source_dir = Path(source_dir).resolve()
    manifest_path = source_dir / "openpeon.json"
    if not manifest_path.exists():
        raise RuntimeError(f"No openpeon.json found in {source_dir}")

    manifest = load_manifest(manifest_path)
    name = str(manifest.get("name", source_dir.name))
    root = packs_root if packs_root is not None else _paths.packs_dir()
    dest = root / name

    if dest.exists():
        if not force:
            raise RuntimeError(f"Pack {name!r} already exists; use force=True to overwrite")
        shutil.rmtree(dest)

    dest.mkdir(parents=True, exist_ok=True)

    # Copy icon if present.
    icon_name = manifest.get("icon")
    if icon_name:
        src_icon = source_dir / icon_name
        if src_icon.exists():
            shutil.copy2(src_icon, dest / icon_name)

    categories = manifest.get("categories", {})
    kept_categories: dict[str, dict[str, Any]] = {}

    for category, entry in categories.items():
        if not isinstance(entry, dict):
            continue
        sounds = entry.get("sounds", [])
        kept_sounds: list[dict[str, Any]] = []
        for sound in sounds:
            src_sound = source_dir / sound["file"]
            if not src_sound.exists():
                continue
            rel_path = Path(sound["file"]).with_suffix(".wav")
            dst_sound = dest / rel_path
            normalize_audio(src_sound, dst_sound)
            kept_sounds.append(
                {
                    **sound,
                    "file": str(rel_path),
                    "label": sound.get("label", ""),
                }
            )
        if kept_sounds:
            kept_categories[category] = {"sounds": kept_sounds}

    manifest["categories"] = kept_categories
    (dest / "openpeon.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return CespPack.from_directory(dest)


def get_active_pack(packs_root: Path | None = None) -> CespPack | None:
    """Return the currently selected CESP pack, or ``None``."""
    cfg = _load_config()
    name = cfg.get("voice", {}).get("active_pack")
    if not name:
        return None
    root = packs_root if packs_root is not None else _paths.packs_dir()
    pack_dir = root / name
    if not (pack_dir / "openpeon.json").exists():
        return None
    return CespPack.from_directory(pack_dir)


def set_active_pack(name: str) -> None:
    """Persist the active CESP pack name."""
    cfg = _load_config()
    cfg.setdefault("voice", {})["active_pack"] = name
    _save_config(cfg)


def list_template_packs() -> list[CespPack]:
    """Scan bundled packs and the directory configured by PURRD_TEMPLATE_PACKS.

    ``PURRD_TEMPLATE_PACKS`` should point to a directory containing one
    subdirectory per pack, each with an ``openpeon.json`` manifest.
    """
    candidates: list[Path] = []

    bundled = bundled_packs_dir()
    if bundled is not None:
        candidates.append(bundled)

    template_root = os.environ.get("PURRD_TEMPLATE_PACKS")
    if template_root:
        candidates.append(Path(template_root))

    packs: list[CespPack] = []
    seen: set[str] = set()
    for root in candidates:
        if not root.exists():
            continue
        for entry in root.iterdir():
            manifest = entry / "openpeon.json"
            if not manifest.exists():
                continue
            try:
                pack = CespPack.from_directory(entry)
                if pack.name in seen:
                    continue
                seen.add(pack.name)
                packs.append(pack)
            except (OSError, ValueError):
                continue
    return sorted(packs, key=lambda p: p.display_name.lower())


def ensure_default_pack() -> CespPack | None:
    """Install and activate the bundled default pack if nothing is active.

    This makes ``purrd say <event>`` work immediately after installation.
    """
    active = get_active_pack()
    if active is not None:
        return active

    bundled = bundled_packs_dir()
    if bundled is None:
        return None

    default_name = "peon"
    default_pack = bundled / default_name
    if not (default_pack / "openpeon.json").exists():
        # Fall back to the first bundled pack available.
        for entry in bundled.iterdir():
            if (entry / "openpeon.json").exists():
                default_pack = entry
                default_name = entry.name
                break
        else:
            return None

    existing = _paths.packs_dir() / default_name
    if existing.exists():
        set_active_pack(default_name)
        return CespPack.from_directory(existing)

    imported = import_pack(default_pack, force=False)
    set_active_pack(imported.name)
    return imported
