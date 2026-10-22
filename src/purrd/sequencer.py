"""Sequencer: assembles the primitives into a loopable lo-fi hip-hop track.

Groove doctrine (see DESIGN.md): the foundation is LOCKED. Drums and bass line
follow fixed patterns that loop — the stable anchor, what the ear holds onto.
Only the melody varies with the seed, to avoid monotony without ever breaking
the steadiness.

Starting with v0.2 the engine also supports named *styles*. The default style
``"classic"`` reproduces the original locked groove byte for byte; other
styles draw from pattern/riff/scale banks so that every seed can produce a
different rhythm, bass line, and harmony.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from . import patterns
from .patterns import Scale
from .synth import (
    SR,
    guitar_chop,
    hat,
    kick,
    pad,
    pluck_bass,
    snare,
    soft_lead,
    strings,
    synth_lead,
    transition_drop,
    transition_fill,
    transition_halt,
    transition_rise,
)

# --- Embedded music theory (the only bit, and it fits in a few lines) ---
# Major pentatonic scale: on this scale, every note works together, so a random
# draw of notes already sounds consonant. That is the trick that makes generative
# music both easy and always pleasant.
_LEAD_ROOT = 261.63  # C4
_LEAD_DEGREES = [-5, -3, 0, 2, 4, 7, 9]  # mid, warm register
_BASS_ROOT = 65.41  # C2

# LOCKED bass riff: step (out of 16) -> degree in semitones. C C G A G E.
_BASS_RIFF = {0: 0, 4: 0, 6: 7, 8: 9, 10: 7, 13: 4}
# Locked drum patterns (boom-bap) on a 16-step grid of sixteenth notes.
_KICK = {0, 6, 10}
_SNARE = {4, 12}  # snare on beats 2 and 4


def _mix(out: np.ndarray, sig: np.ndarray, pos: int) -> None:
    """Add ``sig`` into ``out`` starting at sample ``pos`` (with edge guard)."""
    end = min(pos + sig.size, out.size)
    out[pos:end] += sig[: end - pos]


def _shared_setup(seconds: int, bpm: int) -> tuple[float, int, int]:
    """Compute step duration, bar count, and output buffer size."""
    step = 60 / bpm / 4  # duration of one sixteenth note
    bars = max(1, round(seconds / (step * 16)))
    n = int(SR * step * 16 * bars) + SR  # +1 s of guard for tails
    return step, bars, n


def _postprocess(out: np.ndarray, rng: np.random.Generator, volume: float) -> np.ndarray:
    """Lo-fi patina + normalization."""
    # Lo-fi patina: gentle low-pass (softens), "vinyl" hiss, then a light echo.
    out = np.convolve(out, np.ones(4) / 4, mode="same")
    out += rng.uniform(-1, 1, out.size) * 0.003
    delay = int(0.35 * SR)
    echo = np.zeros(out.size)
    echo[delay:] = out[:-delay] * 0.22
    out += echo

    peak = float(np.max(np.abs(out))) or 1.0
    return (out / (peak * 1.05) * volume).astype(np.float32)


def _build_classic_track(
    seconds: int,
    bpm: int,
    seed: int,
    volume: float,
    progress: Callable[[int, int], None] | None = None,
) -> np.ndarray:
    """Original locked-grove renderer. Kept byte-for-byte for compatibility."""
    step, bars, n = _shared_setup(seconds, bpm)
    rng = np.random.default_rng(seed)
    out = np.zeros(n)

    lead_freqs = [_LEAD_ROOT * 2 ** (s / 12) for s in _LEAD_DEGREES]
    idx = 2  # current position in the melody

    for bar in range(bars):
        for s in range(16):
            pos = int((bar * 16 + s) * step * SR)
            swing = int(0.012 * SR) if s % 2 else 0  # light swing on off-beats
            if s in _KICK:
                _mix(out, kick(), pos)
            if s in _SNARE:
                _mix(out, snare(rng), pos)
            if s % 2 == 0:
                _mix(out, hat(rng, open_=(s % 8 == 4)), pos + swing)
            if s in _BASS_RIFF:  # the bass line (locked)
                freq = _BASS_ROOT * 2 ** (_BASS_RIFF[s] / 12)
                _mix(out, pluck_bass(freq, step * 2.5), pos)
            if s % 4 == 2 and rng.random() < 0.45:  # sparse melody (varies)
                idx = int(np.clip(idx + rng.choice([-1, 0, 1]), 0, len(lead_freqs) - 1))
                _mix(out, soft_lead(lead_freqs[idx], step * 3), pos + swing)

        if progress is not None:
            progress(bar + 1, bars)

    return _postprocess(out, rng, volume)


def _chord_freqs(scale: Scale, lead_freqs: list[float], idx: int) -> list[float]:
    """Return a small chord (root, third, fifth) from ``lead_freqs``."""
    freqs = []
    for offset in (0, 2, 4):
        chord_idx = idx + offset
        if 0 <= chord_idx < len(lead_freqs):
            freqs.append(lead_freqs[chord_idx])
    return freqs if freqs else [lead_freqs[idx]]


_TRANSITION_DUR = 0.55  # seconds; fits in the last four steps of a bar
_TRANSITION_HANDLERS: dict[str, callable] = {
    "rise": transition_rise,
    "fill": transition_fill,
    "drop": transition_drop,
    "halt": transition_halt,
}


def _transition(name: str, rng: np.random.Generator, dur: float) -> np.ndarray:
    """Build a transition effect by name."""
    try:
        return _TRANSITION_HANDLERS[name](rng, dur)
    except KeyError as exc:
        raise ValueError(f"Unknown transition {name!r}") from exc


def _build_styled_track(
    seconds: int,
    bpm: int,
    seed: int,
    volume: float,
    style: str,
    progress: Callable[[int, int], None] | None = None,
) -> np.ndarray:
    """Render a track using the selected style's pattern/riff/scale banks."""
    step, bars, n = _shared_setup(seconds, bpm)
    rng = np.random.default_rng(seed)
    out = np.zeros(n)

    style_obj = patterns.resolve_style(style)
    plans = patterns.arrangement(bars, style_obj, rng)
    scale = plans[0].scale if plans else patterns._SCALES["major_pent"]
    lead_freqs = [scale.root_hz * 2 ** (s / 12) for s in scale.degrees]
    idx = len(lead_freqs) // 2  # start near the middle of the scale

    for bar, plan in enumerate(plans):
        active = plan.active_instruments
        for s in range(16):
            pos = int((bar * 16 + s) * step * SR)
            swing = plan.swing if s % 2 else 0
            if "kick" in active and s in plan.pattern.kick:
                _mix(out, kick(), pos)
            if "snare" in active and s in plan.pattern.snare:
                _mix(out, snare(rng), pos)
            if "hat" in active and (s in plan.pattern.closed_hats or s in plan.pattern.open_hats):
                _mix(out, hat(rng, open_=(s in plan.pattern.open_hats)), pos + swing)
            if "bass" in active and s in plan.riff.steps:
                freq = _BASS_ROOT * 2 ** (plan.riff.steps[s] / 12)
                _mix(out, pluck_bass(freq, step * 2.5), pos)
            if s % 4 == 2 and rng.random() < plan.density:
                idx = int(np.clip(idx + rng.choice([-1, 0, 1]), 0, len(lead_freqs) - 1))
                if "synth_lead" in active:
                    _mix(out, synth_lead(lead_freqs[idx], step * 3), pos + swing)
                elif "lead" in active:
                    _mix(out, soft_lead(lead_freqs[idx], step * 3), pos + swing)
            # Sustained background layers triggered once per bar.
            if s == 0:
                chord = _chord_freqs(scale, lead_freqs, idx)
                if "pad" in active:
                    _mix(out, pad(chord, step * 16), pos)
                if "strings" in active:
                    _mix(out, strings(chord, step * 8), pos)
            # Reggae-style skank: short muted chord chops on every offbeat.
            if "skank" in active and s % 2 == 1:
                chord = _chord_freqs(scale, lead_freqs, idx)
                _mix(out, guitar_chop(chord, step * 1.5), pos + swing)
            # Transition effect on the last beat if this bar ends a section.
            if s == 12 and plan.transition is not None:
                trans = _transition(plan.transition, rng, _TRANSITION_DUR)
                _mix(out, trans, pos)

        if progress is not None:
            progress(bar + 1, bars)

    return _postprocess(out, rng, volume)


def build_track(
    seconds: int = 32,
    bpm: int = 86,
    seed: int = 0,
    volume: float = 1.0,
    style: str = "classic",
    progress: Callable[[int, int], None] | None = None,
) -> np.ndarray:
    """Generate a loop-ready track.

    Args:
        seconds: Target length of the loop.
        bpm: Tempo.
        seed: Controls all randomness.
        volume: Output gain in [0, 1].
        style: Musical preset. ``"classic"`` reproduces the original v0.1 sound;
            other styles draw from pattern/riff/scale banks.

    Returns:
        A normalized mono float32 signal (~[-1, 1]). Deterministic: the same
        ``(seconds, bpm, seed, style, volume)`` yields the same track, byte for
        byte.
    """
    if style == "classic":
        return _build_classic_track(seconds, bpm, seed, volume, progress=progress)
    return _build_styled_track(seconds, bpm, seed, volume, style, progress=progress)
