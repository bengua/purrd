"""Musical pattern banks and deterministic style selection for purrd.

This module is pure (no I/O) and owns every grid, riff, scale, and style used
by the sequencer. It keeps ``sequencer.py`` readable: the sequencer only asks
``arrangement()`` what to play, then plays it.

The public contract:

- ``STYLE_NAMES`` lists the available style presets.
- ``resolve_style(name)`` validates a style name.
- ``arrangement(bars, style, rng)`` returns one :class:`BarPlan` per bar.

For a given ``(bars, style, rng)`` triple the plan is deterministic. The same
``np.random.Generator`` is passed in by the sequencer, so ``(seconds, bpm, seed,
style, volume)`` yields byte-for-byte identical output.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# ---------------------------------------------------------------------------
# Shared constants (Hz)
# ---------------------------------------------------------------------------
_C4 = 261.63
_C2 = 65.41
_A3 = 220.00
_D4 = 293.66

# Instruments available to every style. The default set reproduces the original
# engine: kick, snare, hi-hat, bass, and the soft lead melody.
DEFAULT_INSTRUMENTS: tuple[str, ...] = ("kick", "snare", "hat", "bass", "lead")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Scale:
    """Diatonic collection used by the lead melody."""

    name: str
    root_hz: float
    degrees: tuple[int, ...]
    """Semitone offsets from ``root_hz``. Negative degrees are allowed."""


@dataclass(frozen=True)
class DrumPattern:
    """One 16-step drum grid."""

    name: str
    kick: frozenset[int]
    snare: frozenset[int]
    closed_hats: frozenset[int]
    open_hats: frozenset[int]


@dataclass(frozen=True)
class BassRiff:
    """Bass line: step (0..15) -> semitone degree relative to the bass root."""

    name: str
    steps: dict[int, int]


@dataclass(frozen=True)
class Style:
    """A musical preset that selects from the pattern/riff/scale banks."""

    name: str
    allowed_patterns: tuple[str, ...]
    allowed_riffs: tuple[str, ...]
    scale_name: str
    densities: dict[str, float]
    structure_cycle: tuple[str, ...]
    swing: float
    active_instruments: tuple[str, ...] = DEFAULT_INSTRUMENTS
    transitions: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BarPlan:
    """Everything needed to render one bar."""

    pattern: DrumPattern
    riff: BassRiff
    scale: Scale
    density: float
    section: str
    swing: int
    active_instruments: tuple[str, ...] = DEFAULT_INSTRUMENTS
    transition: str | None = None


# ---------------------------------------------------------------------------
# Scales
# ---------------------------------------------------------------------------
_SCALES: dict[str, Scale] = {
    "major_pent": Scale(
        "major_pent",
        _C4,
        (-5, -3, 0, 2, 4, 7, 9),
    ),
    "minor_pent": Scale(
        "minor_pent",
        _A3,
        (-5, -3, 0, 2, 3, 7, 10),
    ),
    "dorian_pent": Scale(
        "dorian_pent",
        _D4,
        (-7, -5, -2, 0, 2, 5, 9),
    ),
    "dreamy": Scale(
        "dreamy",
        _C4,
        (-5, -3, 0, 2, 4, 7, 9, 11),
    ),
}

# ---------------------------------------------------------------------------
# Drum patterns
# ---------------------------------------------------------------------------
_DRUM_PATTERNS: dict[str, DrumPattern] = {
    "boom_bap": DrumPattern(
        "boom_bap",
        kick=frozenset({0, 6, 10}),
        snare=frozenset({4, 12}),
        closed_hats=frozenset({0, 2, 4, 6, 8, 10, 12, 14}),
        open_hats=frozenset({4}),
    ),
    "boom_bap_fill": DrumPattern(
        "boom_bap_fill",
        kick=frozenset({0, 6, 10, 14}),
        snare=frozenset({4, 12, 15}),
        closed_hats=frozenset({0, 2, 4, 6, 8, 10, 12, 14}),
        open_hats=frozenset({4, 12}),
    ),
    "kick_swing": DrumPattern(
        "kick_swing",
        kick=frozenset({0, 3, 10}),
        snare=frozenset({4, 12}),
        closed_hats=frozenset(range(16)),
        open_hats=frozenset({4}),
    ),
    "spaced": DrumPattern(
        "spaced",
        kick=frozenset({0, 8}),
        snare=frozenset({4, 12}),
        closed_hats=frozenset({0, 4, 8, 12}),
        open_hats=frozenset(),
    ),
    "drive": DrumPattern(
        "drive",
        kick=frozenset({0, 6, 8, 10}),
        snare=frozenset({4, 12}),
        closed_hats=frozenset({0, 2, 4, 6, 8, 10, 12, 14}),
        open_hats=frozenset({4, 12}),
    ),
    "minimal": DrumPattern(
        "minimal",
        kick=frozenset({0}),
        snare=frozenset({8}),
        closed_hats=frozenset({0, 8}),
        open_hats=frozenset(),
    ),
    "jazz_swing": DrumPattern(
        "jazz_swing",
        kick=frozenset({0, 4, 8, 12}),
        snare=frozenset({4, 8, 12, 14}),
        closed_hats=frozenset(range(16)),
        open_hats=frozenset({4, 12}),
    ),
    "ambient_sparse": DrumPattern(
        "ambient_sparse",
        kick=frozenset({0, 9}),
        snare=frozenset({12}),
        closed_hats=frozenset({0, 8}),
        open_hats=frozenset({8}),
    ),
    "reggae_skank": DrumPattern(
        "reggae_skank",
        kick=frozenset({0, 10}),
        snare=frozenset({4, 12}),
        closed_hats=frozenset({1, 3, 5, 7, 9, 11, 13, 15}),
        open_hats=frozenset(),
    ),
    "trap_bounce": DrumPattern(
        "trap_bounce",
        kick=frozenset({0, 3, 7, 10, 14}),
        snare=frozenset({4, 8, 12, 14}),
        closed_hats=frozenset(range(16)),
        open_hats=frozenset({4, 12}),
    ),
    "funky_ghost": DrumPattern(
        "funky_ghost",
        kick=frozenset({0, 3, 6, 10, 14}),
        snare=frozenset({4, 12, 14}),
        closed_hats=frozenset({0, 2, 4, 6, 8, 10, 12, 14}),
        open_hats=frozenset({4}),
    ),
    "techno_four": DrumPattern(
        "techno_four",
        kick=frozenset({0, 4, 8, 12}),
        snare=frozenset({4, 12}),
        closed_hats=frozenset({1, 3, 5, 7, 9, 11, 13, 15}),
        open_hats=frozenset({2, 6, 10, 14}),
    ),
    "latin_clave": DrumPattern(
        "latin_clave",
        kick=frozenset({0, 7, 10}),
        snare=frozenset({3, 6, 9, 12, 14}),
        closed_hats=frozenset({2, 5, 8, 11, 14}),
        open_hats=frozenset(),
    ),
    "hardrock_backbeat": DrumPattern(
        "hardrock_backbeat",
        kick=frozenset({0, 6, 10, 14}),
        snare=frozenset({4, 8, 12}),
        closed_hats=frozenset({0, 2, 4, 6, 8, 10, 12, 14}),
        open_hats=frozenset({4, 12}),
    ),
    "house_groove": DrumPattern(
        "house_groove",
        kick=frozenset({0, 4, 8, 12}),
        snare=frozenset({5, 13}),
        closed_hats=frozenset({1, 3, 5, 7, 9, 11, 13, 15}),
        open_hats=frozenset({7, 15}),
    ),
}

# ---------------------------------------------------------------------------
# Bass riffs
# ---------------------------------------------------------------------------
_BASS_RIFFS: dict[str, BassRiff] = {
    "classic": BassRiff(
        "classic",
        {0: 0, 4: 0, 6: 7, 8: 9, 10: 7, 13: 4},
    ),
    "root_fifth": BassRiff(
        "root_fifth",
        {0: 0, 4: 7, 8: 0, 12: 7},
    ),
    "syncopated": BassRiff(
        "syncopated",
        {2: 0, 5: 7, 10: 4, 13: 9},
    ),
    "sparse_octaves": BassRiff(
        "sparse_octaves",
        {0: 0, 8: 12},
    ),
    "walking": BassRiff(
        "walking",
        {0: 0, 2: 2, 4: 4, 6: 5, 8: 7, 10: 9, 12: 7, 14: 4},
    ),
    "funky_bounce": BassRiff(
        "funky_bounce",
        {0: 0, 2: 4, 4: 5, 6: 7, 8: 9, 10: 7, 12: 4, 14: 0},
    ),
    "techno_pulse": BassRiff(
        "techno_pulse",
        {0: 0, 4: 12, 8: 7, 12: 0},
    ),
    "latin_bass": BassRiff(
        "latin_bass",
        {0: 0, 3: 5, 6: 7, 10: 9, 13: 5},
    ),
    "triphop_sub": BassRiff(
        "triphop_sub",
        {0: 0, 8: 0},
    ),
    "hardrock_riff": BassRiff(
        "hardrock_riff",
        {0: 0, 4: 3, 6: 5, 8: 7, 10: 5, 12: 3, 14: 0},
    ),
    "house_bass": BassRiff(
        "house_bass",
        {0: 0, 3: 7, 7: 12, 10: 7},
    ),
}

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
_STYLES: dict[str, Style] = {
    "classic": Style(
        name="classic",
        allowed_patterns=("boom_bap",),
        allowed_riffs=("classic",),
        scale_name="major_pent",
        densities={"verse": 0.45},
        structure_cycle=("verse",),
        swing=0.012,
    ),
    "chill": Style(
        name="chill",
        allowed_patterns=("spaced", "minimal", "boom_bap"),
        allowed_riffs=("root_fifth", "sparse_octaves", "classic"),
        scale_name="dreamy",
        densities={"intro": 0.20, "verse": 0.30, "chorus": 0.45, "outro": 0.15},
        structure_cycle=("intro", "verse", "verse", "chorus", "outro"),
        swing=0.018,
        transitions={"verse": "rise", "chorus": "drop"},
    ),
    "drive": Style(
        name="drive",
        allowed_patterns=("drive", "kick_swing", "boom_bap_fill"),
        allowed_riffs=("classic", "walking", "syncopated"),
        scale_name="major_pent",
        densities={"verse": 0.50, "chorus": 0.65, "break": 0.35},
        structure_cycle=("verse", "chorus", "verse", "break", "chorus"),
        swing=0.008,
        transitions={"verse": "rise", "chorus": "halt", "break": "fill"},
    ),
    "noir": Style(
        name="noir",
        allowed_patterns=("spaced", "minimal", "boom_bap_fill"),
        allowed_riffs=("root_fifth", "syncopated", "sparse_octaves"),
        scale_name="minor_pent",
        densities={"intro": 0.25, "verse": 0.35, "chorus": 0.45, "break": 0.30},
        structure_cycle=("intro", "verse", "verse", "chorus", "break", "verse"),
        swing=0.015,
        transitions={"verse": "halt", "chorus": "drop"},
    ),
    "minimal": Style(
        name="minimal",
        allowed_patterns=("minimal", "spaced"),
        allowed_riffs=("sparse_octaves", "root_fifth"),
        scale_name="dorian_pent",
        densities={"intro": 0.15, "verse": 0.25, "chorus": 0.35, "outro": 0.10},
        structure_cycle=("intro", "verse", "chorus", "outro"),
        swing=0.020,
        transitions={"verse": "rise"},
    ),
    "jazz": Style(
        name="jazz",
        allowed_patterns=("jazz_swing", "kick_swing", "boom_bap_fill"),
        allowed_riffs=("walking", "syncopated", "classic"),
        scale_name="dorian_pent",
        densities={"verse": 0.50, "chorus": 0.60, "break": 0.45},
        structure_cycle=("verse", "verse", "chorus", "break", "chorus"),
        swing=0.030,
        active_instruments=("kick", "snare", "hat", "bass", "lead", "strings", "pad"),
        transitions={"verse": "fill", "chorus": "halt"},
    ),
    "ambient": Style(
        name="ambient",
        allowed_patterns=("ambient_sparse", "spaced", "minimal"),
        allowed_riffs=("sparse_octaves", "root_fifth"),
        scale_name="dreamy",
        densities={"intro": 0.10, "verse": 0.18, "chorus": 0.25, "outro": 0.08},
        structure_cycle=("intro", "verse", "verse", "chorus", "verse", "outro"),
        swing=0.008,
        active_instruments=("kick", "snare", "hat", "bass", "lead", "pad", "strings"),
        transitions={"verse": "rise", "chorus": "drop"},
    ),
    "reggae": Style(
        name="reggae",
        allowed_patterns=("reggae_skank", "spaced"),
        allowed_riffs=("classic", "syncopated", "root_fifth"),
        scale_name="major_pent",
        densities={"verse": 0.35, "chorus": 0.45, "break": 0.30},
        structure_cycle=("verse", "chorus", "verse", "break", "chorus"),
        swing=0.015,
        active_instruments=("kick", "snare", "hat", "bass", "lead", "skank"),
        transitions={"verse": "fill", "chorus": "halt"},
    ),
    "trap": Style(
        name="trap",
        allowed_patterns=("trap_bounce", "boom_bap_fill", "drive"),
        allowed_riffs=("root_fifth", "syncopated"),
        scale_name="minor_pent",
        densities={"verse": 0.40, "chorus": 0.55, "break": 0.35},
        structure_cycle=("verse", "chorus", "verse", "break", "chorus"),
        swing=0.010,
        active_instruments=("kick", "snare", "hat", "bass", "synth_lead"),
        transitions={"verse": "rise", "chorus": "drop", "break": "fill"},
    ),
    "funky": Style(
        name="funky",
        allowed_patterns=("funky_ghost", "kick_swing", "boom_bap"),
        allowed_riffs=("funky_bounce", "syncopated", "classic"),
        scale_name="major_pent",
        densities={"verse": 0.45, "chorus": 0.60, "break": 0.50},
        structure_cycle=("verse", "verse", "chorus", "break", "chorus"),
        swing=0.018,
        active_instruments=("kick", "snare", "hat", "bass", "synth_lead"),
        transitions={"verse": "fill", "chorus": "rise"},
    ),
    "techno": Style(
        name="techno",
        allowed_patterns=("techno_four", "drive", "minimal"),
        allowed_riffs=("techno_pulse", "root_fifth", "sparse_octaves"),
        scale_name="minor_pent",
        densities={"verse": 0.40, "build": 0.55, "drop": 0.65},
        structure_cycle=("verse", "verse", "build", "drop", "verse"),
        swing=0.006,
        active_instruments=("kick", "snare", "hat", "bass", "synth_lead", "pad"),
        transitions={"verse": "rise", "build": "fill", "drop": "halt"},
    ),
    "latin": Style(
        name="latin",
        allowed_patterns=("latin_clave", "reggae_skank", "spaced"),
        allowed_riffs=("latin_bass", "syncopated", "walking"),
        scale_name="dorian_pent",
        densities={"verse": 0.45, "chorus": 0.55, "break": 0.40},
        structure_cycle=("verse", "chorus", "verse", "break", "chorus"),
        swing=0.012,
        active_instruments=("kick", "snare", "hat", "bass", "lead", "strings"),
        transitions={"verse": "rise", "chorus": "drop"},
    ),
    "triphop": Style(
        name="triphop",
        allowed_patterns=("ambient_sparse", "spaced", "boom_bap"),
        allowed_riffs=("triphop_sub", "sparse_octaves", "root_fifth"),
        scale_name="dreamy",
        densities={"intro": 0.12, "verse": 0.20, "chorus": 0.30, "outro": 0.10},
        structure_cycle=("intro", "verse", "verse", "chorus", "outro"),
        swing=0.025,
        active_instruments=("kick", "snare", "hat", "bass", "lead", "pad", "strings"),
        transitions={"verse": "rise", "chorus": "drop"},
    ),
    "hardrock": Style(
        name="hardrock",
        allowed_patterns=("hardrock_backbeat", "drive", "boom_bap_fill"),
        allowed_riffs=("hardrock_riff", "root_fifth", "walking"),
        scale_name="minor_pent",
        densities={"verse": 0.55, "chorus": 0.70, "break": 0.45},
        structure_cycle=("verse", "chorus", "verse", "break", "chorus"),
        swing=0.008,
        active_instruments=("kick", "snare", "hat", "bass", "lead"),
        transitions={"verse": "rise", "chorus": "halt", "break": "fill"},
    ),
    "house": Style(
        name="house",
        allowed_patterns=("house_groove", "techno_four", "minimal"),
        allowed_riffs=("house_bass", "root_fifth", "sparse_octaves"),
        scale_name="major_pent",
        densities={
            "intro": 0.20,
            "verse": 0.40,
            "chorus": 0.55,
            "build": 0.60,
            "outro": 0.20,
        },
        structure_cycle=("intro", "verse", "chorus", "build", "chorus", "outro"),
        swing=0.008,
        active_instruments=("kick", "snare", "hat", "bass", "synth_lead", "pad"),
        transitions={"verse": "rise", "chorus": "drop", "build": "fill"},
    ),
}

STYLE_NAMES: tuple[str, ...] = tuple(_STYLES.keys())


def resolve_style(name: str) -> Style:
    """Return the :class:`Style` called ``name``.

    Raises:
        ValueError: if the style is unknown.
    """
    try:
        return _STYLES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown style {name!r}; choose from {STYLE_NAMES}") from exc


def _choice(rng: np.random.Generator, options: tuple[str, ...]) -> str:
    """Deterministically pick one name from ``options``."""
    if len(options) == 1:
        return options[0]
    idx = int(rng.integers(0, len(options)))
    return options[idx]


def arrangement(bars: int, style: Style, rng: np.random.Generator) -> list[BarPlan]:
    """Build a deterministic bar-by-bar plan for the requested style.

    For each section type in ``style.structure_cycle`` a single drum pattern
    and bass riff are chosen. Those choices persist for every occurrence of
    the section, giving the track coherent phrases that still differ across
    seeds and styles.

    Args:
        bars: Number of bars in the track.
        style: The musical preset selected by the user/seed.
        rng: The sequencer's RNG. All draws happen here so the whole track is
            reproducible for a given seed.

    Returns:
        A list of length ``bars`` describing what to play each bar.
    """
    scale = _SCALES[style.scale_name]
    sample_rate = 44_100  # mirrored from synth.SR to avoid a circular import
    swing_samples = int(style.swing * sample_rate)

    # Pre-select one pattern + riff per unique section in the cycle so that
    # repeated sections stay coherent instead of changing every bar.
    unique_sections = tuple(dict.fromkeys(style.structure_cycle))
    section_patterns: dict[str, DrumPattern] = {}
    section_riffs: dict[str, BassRiff] = {}
    for section in unique_sections:
        pattern_name = _choice(rng, style.allowed_patterns)
        riff_name = _choice(rng, style.allowed_riffs)
        section_patterns[section] = _DRUM_PATTERNS[pattern_name]
        section_riffs[section] = _BASS_RIFFS[riff_name]

    plans: list[BarPlan] = []
    cycle_len = len(style.structure_cycle)
    for bar in range(bars):
        section = style.structure_cycle[bar % cycle_len]
        # Flip to a fresh pattern/riff every 4 bars for long tracks, keeping the
        # same section family but adding a little evolution.
        if bar > 0 and bar % 4 == 0:
            pattern_name = _choice(rng, style.allowed_patterns)
            riff_name = _choice(rng, style.allowed_riffs)
            section_patterns[section] = _DRUM_PATTERNS[pattern_name]
            section_riffs[section] = _BASS_RIFFS[riff_name]

        density = style.densities.get(section, 0.45)

        # Detect section boundaries and assign a transition to the last bar of
        # the outgoing section if the style defines one.
        next_section = style.structure_cycle[(bar + 1) % cycle_len]
        transition: str | None = None
        if bar < bars - 1 and section != next_section:
            transition = style.transitions.get(section)

        plans.append(
            BarPlan(
                pattern=section_patterns[section],
                riff=section_riffs[section],
                scale=scale,
                density=density,
                section=section,
                swing=swing_samples,
                active_instruments=style.active_instruments,
                transition=transition,
            )
        )
    return plans
