"""Every style must render a valid, non-empty, correctly shaped track.

A broken style would only surface at runtime as silence or a crash; this loops
over the authoritative style list so a new style is covered automatically.
"""

from __future__ import annotations

import pytest

from purrd.patterns import STYLE_NAMES
from purrd.player import to_pcm16
from purrd.sequencer import build_track
from purrd.synth import SR

SECONDS = 4


@pytest.mark.parametrize("style", STYLE_NAMES)
def test_style_renders_valid_pcm(style: str) -> None:
    pcm = to_pcm16(build_track(seconds=SECONDS, bpm=90, seed=1, style=style))
    assert isinstance(pcm, bytes)
    assert pcm  # non-empty
    assert len(pcm) % 2 == 0  # s16 samples
    frames = len(pcm) // 2
    expected = SECONDS * SR
    # Generous tolerance: styles may round the loop to a bar, but it must be in
    # the right ballpark, not a stub or a runaway.
    assert 0.5 * expected <= frames <= 2.0 * expected, (
        f"{style}: {frames} frames, expected ~{expected}"
    )


def test_the_style_list_is_not_empty():
    assert len(STYLE_NAMES) >= 1
