"""Sound synthesis primitives — pure functions, no I/O, hence testable.

Each function returns a mono signal as a float ``np.ndarray`` with values in
roughly [-1, 1]. This is the *auditable core* of purrd: a human reads this file
in five minutes and understands where every sound comes from. The reasoning
behind each choice is commented.
"""

from __future__ import annotations

import numpy as np

SR = 44100  # sample rate = CD quality (see DESIGN.md, "Technical choices")


def _pluck_env(n: int, attack: float = 0.008, decay: float = 3.5) -> np.ndarray:
    """Plucked envelope: soft attack (no click) followed by exponential decay."""
    t = np.arange(n) / SR
    return np.minimum(1.0, t / attack) * np.exp(-t * decay)


def kick(dur: float = 0.30) -> np.ndarray:
    """Kick drum: a sine whose pitch drops fast, producing the "boom"."""
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    freq = 120 * np.exp(-t * 28) + 48  # pitch drop from ~168 Hz to 48 Hz
    phase = 2 * np.pi * np.cumsum(freq) / SR
    return np.sin(phase) * np.exp(-t * 7) * 0.9


def snare(rng: np.random.Generator, dur: float = 0.22) -> np.ndarray:
    """Snare: noise (the "tss") plus a hint of 180 Hz tone (the body).

    The RNG is passed in rather than created here, so the function stays
    deterministic for a given seed and is therefore testable (see tests).
    """
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    noise = rng.uniform(-1, 1, t.size)
    tone = np.sin(2 * np.pi * 180 * t) * 0.3
    return (noise * 0.7 + tone) * np.exp(-t * 17) * 0.55


def hat(rng: np.random.Generator, open_: bool = False) -> np.ndarray:
    """Hi-hat: noise run through a crude high-pass (np.diff) with a short envelope."""
    dur = 0.09 if open_ else 0.045
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    noise = np.diff(rng.uniform(-1, 1, t.size), prepend=0.0)
    return noise * np.exp(-t * (16 if open_ else 38)) * 0.30


def pluck_bass(freq: float, dur: float) -> np.ndarray:
    """Bass: fundamental plus two harmonics for body, with a plucked envelope.

    This is the instrument that carries the groove (the locked bass line).
    """
    n = int(SR * dur)
    t = np.arange(n) / SR
    wave = (
        np.sin(2 * np.pi * freq * t)
        + 0.30 * np.sin(2 * np.pi * 2 * freq * t)
        + 0.12 * np.sin(2 * np.pi * 3 * freq * t)
    )
    return wave * _pluck_env(n) * 0.21


def soft_lead(freq: float, dur: float) -> np.ndarray:
    """Melody: soft timbre (few harmonics), low volume, mid register.

    Deliberately understated: it floats over the groove without demanding attention.
    """
    n = int(SR * dur)
    t = np.arange(n) / SR
    wave = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(2 * np.pi * 2 * freq * t)
    env = np.exp(-t / 0.9)
    a = int(0.012 * SR)
    env[:a] *= np.linspace(0, 1, a)  # soft attack = no click
    return wave * env * 0.11


def pad(freqs: list[float], dur: float) -> np.ndarray:
    """Sustained pad: layered detuned saw-like waves, slow attack and release.

    ``freqs`` should contain the root and one or two chord tones; multiple
    oscillators are detuned slightly for warmth.
    """
    n = int(SR * dur)
    t = np.arange(n) / SR
    wave = np.zeros(n)
    for base in freqs:
        for detune in (-0.003, 0.003):
            f = base * (1 + detune)
            wave += np.sin(2 * np.pi * f * t)
            wave += 0.35 * np.sin(2 * np.pi * 2 * f * t)
    wave /= max(1.0, len(freqs) * 2.7)

    attack = int(0.18 * SR)
    release = int(0.9 * SR)
    env = np.ones(n)
    if attack > 0:
        env[:attack] *= np.linspace(0, 1, attack)
    if release > 0 and n - release > 0:
        env[-release:] *= np.linspace(1, 0, release)
    # Gentle low-pass via moving average.
    kernel = np.ones(5) / 5
    wave = np.convolve(wave, kernel, mode="same")
    return wave * env * 0.18


def strings(freqs: list[float], dur: float) -> np.ndarray:
    """String ensemble: slow vibrato, sustained bowed envelope.

    ``freqs`` contains the chord tones (typically root, third, fifth).
    """
    n = int(SR * dur)
    t = np.arange(n) / SR
    vibrato = 1.0 + 0.015 * np.sin(2 * np.pi * 5.5 * t)
    wave = np.zeros(n)
    for f in freqs:
        wave += np.sin(2 * np.pi * f * t * vibrato)
        wave += 0.12 * np.sin(2 * np.pi * 2 * f * t)
    wave /= max(1.0, len(freqs) * 1.12)
    env = _pluck_env(n, attack=0.06, decay=0.7)
    return wave * env * 0.22


def synth_lead(freq: float, dur: float) -> np.ndarray:
    """Brighter lead: square-like harmonics, faster attack than soft_lead."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    wave = (
        np.sin(2 * np.pi * freq * t)
        + 0.30 * np.sin(2 * np.pi * 3 * freq * t) / 3
        + 0.15 * np.sin(2 * np.pi * 5 * freq * t) / 5
    )
    attack = int(0.025 * SR)
    env = np.exp(-t / 0.55)
    if attack > 0:
        env[:attack] *= np.linspace(0, 1, attack)
    return wave * env * 0.08


def guitar_chop(freqs: list[float], dur: float = 0.08) -> np.ndarray:
    """Short, staccato reggae skank chord.

    A percussive, muted up-strum on the offbeat. Multiple chord tones are
    layered with a very fast attack and tight decay so it sits between drums
    and melody without sustaining.
    """
    n = int(SR * dur)
    t = np.arange(n) / SR
    wave = np.zeros(n)
    for f in freqs:
        wave += np.sin(2 * np.pi * f * t)
        wave += 0.25 * np.sin(2 * np.pi * 2 * f * t)
    wave /= max(1.0, len(freqs))

    attack = int(0.005 * SR)
    env = _pluck_env(n, attack=0.005, decay=12.0)
    if attack > 0:
        env[:attack] *= np.linspace(0, 1, attack)
    return wave * env * 0.25


def transition_rise(rng: np.random.Generator, dur: float) -> np.ndarray:
    """Rising transition: a smooth frequency sweep that climbs into the next section.

    Keeps a low amplitude so it stays in the background.
    """
    n = int(SR * dur)
    t = np.arange(n) / SR
    # Exponential sweep from 200 Hz up to ~4 kHz.
    f0, f1 = 200.0, 4000.0
    freq = f0 * (f1 / f0) ** (t / dur)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    wave = np.sin(phase)
    # Add a little noise sheen on top.
    noise = rng.uniform(-1, 1, n) * 0.25
    env = np.linspace(0, 1, n) * np.linspace(1, 0, n)
    return (wave * 0.6 + noise) * env * 0.12


def transition_fill(rng: np.random.Generator, dur: float) -> np.ndarray:
    """Fill transition: a short burst of noise and snare-ish body."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    noise = rng.uniform(-1, 1, n)
    tone = np.sin(2 * np.pi * 220 * t) * 0.3
    # Build energy over the first half then decay.
    attack = n // 2
    env = np.concatenate((np.linspace(0, 1, attack), np.linspace(1, 0, n - attack)))
    return (noise * 0.7 + tone) * env * np.exp(-t * 6) * 0.28


def transition_drop(rng: np.random.Generator, dur: float) -> np.ndarray:
    """Drop transition: a low kick thump followed by a quick tail fade.

    Useful to mark a section landing/change without adding high-frequency clutter.
    """
    n = int(SR * dur)
    t = np.arange(n) / SR
    # Pitch-drop body like a kick but shorter.
    freq = 90 * np.exp(-t * 35) + 40
    phase = 2 * np.pi * np.cumsum(freq) / SR
    body = np.sin(phase) * np.exp(-t * 12)
    env = np.linspace(1, 0, n) ** 1.5
    return body * env * 0.45


def transition_halt(rng: np.random.Generator, dur: float) -> np.ndarray:
    """Halt transition: a fast reverse-noise hit that signals a hard cut."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    noise = rng.uniform(-1, 1, n)
    # Reverse envelope: loud attack that dies quickly.
    env = np.linspace(1, 0, n) * np.exp(-t * 14)
    return noise * env * 0.22
