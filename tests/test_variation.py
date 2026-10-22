"""Tests that the style-aware engine produces variety without breaking determinism.

These tests complement ``test_synth.py``. They prove that:

1. The default build path still equals the ``classic`` style (backward compatibility).
2. Every style is reproducible for the same (seconds, bpm, seed, style, volume).
3. Different seeds produce different tracks within a style.
4. Different styles produce different tracks for the same seed.
5. All styles stay bounded and finite.
"""

import numpy as np
import pytest

from purrd import patterns
from purrd.patterns import STYLE_NAMES
from purrd.sequencer import build_track
from purrd.synth import SR


@pytest.mark.parametrize("style", STYLE_NAMES)
def test_style_is_reproducible(style: str):
    a = build_track(seconds=8, bpm=86, seed=42, style=style)
    b = build_track(seconds=8, bpm=86, seed=42, style=style)
    assert a.dtype == np.float32
    assert np.array_equal(a, b)


def test_default_equals_classic():
    assert np.array_equal(
        build_track(8, 86, 7),
        build_track(8, 86, 7, style="classic"),
    )


@pytest.mark.parametrize("style", STYLE_NAMES)
def test_seed_changes_the_track_within_style(style: str):
    a = build_track(8, 86, 1, style=style)
    b = build_track(8, 86, 2, style=style)
    assert not np.array_equal(a, b)


def test_styles_sound_different_for_same_seed():
    base = build_track(8, 86, 7, style="classic")
    for style in STYLE_NAMES:
        if style == "classic":
            continue
        variant = build_track(8, 86, 7, style=style)
        assert not np.array_equal(base, variant), f"style {style!r} equals classic"


def test_styles_stay_bounded_and_finite():
    for style in STYLE_NAMES:
        buf = build_track(8, 86, seed=123, style=style)
        assert np.all(np.isfinite(buf))
        assert np.max(np.abs(buf)) <= 1.0
        assert SR * 6 < buf.size < SR * 12


def test_new_styles_are_registered():
    new_styles = {
        "jazz",
        "ambient",
        "reggae",
        "trap",
        "funky",
        "techno",
        "latin",
        "triphop",
        "hardrock",
        "house",
    }
    assert new_styles <= set(STYLE_NAMES)


def _style_scale_name(style: str) -> str:
    from purrd import patterns

    style_obj = patterns.resolve_style(style)
    plan = patterns.arrangement(4, style_obj, np.random.default_rng(42))
    return plan[0].scale.name


def test_jazz_uses_dorian_pent():
    assert _style_scale_name("jazz") == "dorian_pent"


def test_ambient_uses_dreamy():
    assert _style_scale_name("ambient") == "dreamy"


def test_reggae_uses_major_pent():
    assert _style_scale_name("reggae") == "major_pent"


def test_trap_uses_minor_pent():
    assert _style_scale_name("trap") == "minor_pent"


def test_funky_uses_major_pent():
    assert _style_scale_name("funky") == "major_pent"


def test_techno_uses_minor_pent():
    assert _style_scale_name("techno") == "minor_pent"


def test_latin_uses_dorian_pent():
    assert _style_scale_name("latin") == "dorian_pent"


def test_triphop_uses_dreamy():
    assert _style_scale_name("triphop") == "dreamy"


def test_hardrock_uses_minor_pent():
    assert _style_scale_name("hardrock") == "minor_pent"


def test_house_uses_major_pent():
    assert _style_scale_name("house") == "major_pent"


def test_styles_with_multiple_sections_have_section_transitions():
    """Styles that change section should mark at least one boundary."""
    for style_name in STYLE_NAMES:
        style = patterns.resolve_style(style_name)
        if len(set(style.structure_cycle)) == 1:
            continue
        plans = patterns.arrangement(8, style, np.random.default_rng(42))
        transitions = [p.transition for p in plans]
        assert any(t is not None for t in transitions), (
            f"style {style_name!r} has no transitions despite multiple sections"
        )


def test_last_bar_never_has_transition():
    """A transition points forward, so the final bar has nothing to transition to."""
    for style_name in STYLE_NAMES:
        style = patterns.resolve_style(style_name)
        plans = patterns.arrangement(8, style, np.random.default_rng(42))
        assert plans[-1].transition is None, f"style {style_name!r} transitions on last bar"
