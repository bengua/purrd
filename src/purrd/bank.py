"""Pre-generated ambience bank — ready audio files, no model at runtime.

The bank is an alternative to the synth engine: a directory of finished tracks
(``mp3``/``wav``/``flac``/``ogg``/``opus``/``m4a``) picked with a weighted
alternation against synthesis (config ``[bank].ratio``). The helpers here are
pure except ``decode_pcm``, which shells out to ffmpeg — an optional
dependency: a missing or failing ffmpeg degrades to synth-only (empty bytes).
"""

from __future__ import annotations

import random
import subprocess
from pathlib import Path

import numpy as np

from purrd import _paths
from purrd import config
from purrd.synth import SR


# Audio suffixes accepted in the bank (case-insensitive).
BANK_SUFFIXES = {".mp3", ".wav", ".flac", ".ogg", ".opus", ".m4a"}

# Target RMS level for bank tracks, so they sit at the same perceived level as
# the synth engine (bank tracks measured 6-7 dB hotter, peaking at 0.0 dBFS).
TARGET_RMS_DBFS = -17.0

# Peak ceiling after gain: full scale is never allowed.
MAX_PEAK_DBFS = -1.0


def normalise_pcm(pcm: bytes) -> bytes:
    """Rescale s16le mono PCM to ``TARGET_RMS_DBFS`` with a single constant gain.

    The gain is further reduced, when needed, so the resulting peak never
    exceeds ``MAX_PEAK_DBFS``. No per-block compression or limiting: the point
    is to preserve the dynamics the model produced. Empty input yields empty
    output; silent input (zero RMS) is returned unchanged rather than divided
    by zero.
    """
    if not pcm:
        return b""
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
    rms = float(np.sqrt(np.mean(samples**2)))
    if rms == 0.0:
        return pcm
    target_rms = 32768.0 * (10.0 ** (TARGET_RMS_DBFS / 20.0))
    gain = target_rms / rms
    peak = float(np.max(np.abs(samples)))
    max_peak = 32768.0 * (10.0 ** (MAX_PEAK_DBFS / 20.0))
    gain = min(gain, max_peak / peak)
    return np.clip(samples * gain, -32768.0, 32767.0).astype("<i2").tobytes()


def list_bank() -> list[Path]:
    """Return the bank's audio files, sorted by name.

    Files directly in ``bank_dir()`` whose suffix is in ``BANK_SUFFIXES``
    (case-insensitive). An absent or unreadable directory yields ``[]``, never
    an exception.
    """
    directory = _paths.bank_dir()
    try:
        entries = sorted(directory.iterdir(), key=lambda p: p.name)
    except OSError:
        return []
    return [p for p in entries if p.is_file() and p.suffix.lower() in BANK_SUFFIXES]


def bank_ratio() -> float:
    """Fraction of tracks that should come from the bank, from ``[bank].ratio``.

    Reads the user config; defaults to ``0.0`` when the section or key is
    absent or not a number, and clamps the result into ``[0.0, 1.0]``.
    """
    value = config.load().get("bank", {}).get("ratio")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return max(0.0, min(1.0, float(value)))


def pick_track(ratio: float, rng: random.Random | None = None) -> Path | None:
    """Pick a bank track with probability ``ratio``; ``None`` means synthesize.

    ``ratio`` is clamped into ``[0.0, 1.0]``. An empty bank always yields
    ``None``; otherwise a file is chosen only when the draw is below ``ratio``.
    """
    if rng is None:
        rng = random
    ratio = max(0.0, min(1.0, ratio))
    files = list_bank()
    if not files or rng.random() >= ratio:
        return None
    return rng.choice(files)


def decode_pcm(path: Path) -> bytes:
    """Decode ``path`` to level-matched raw s16le mono PCM at ``SR`` Hz.

    The ffmpeg output is passed through ``normalise_pcm`` so every caller gets
    a track at the same perceived level as the synth engine. Returns the bytes,
    or ``b""`` on any failure (ffmpeg missing, non-zero exit, ``OSError``) so
    callers can fall back to synthesis.
    """
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(path),
        "-f",
        "s16le",
        "-ar",
        str(SR),
        "-ac",
        "1",
        "-",
    ]
    try:
        proc = subprocess.run(command, capture_output=True, check=False)
    except OSError:
        return b""
    if proc.returncode != 0:
        return b""
    return normalise_pcm(proc.stdout)
