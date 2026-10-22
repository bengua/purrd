"""Tests for the pure core. They double as usage documentation for the primitives."""

import numpy as np
import pytest

from purrd.synth import (
    SR,
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
from purrd.sequencer import build_track


def test_kick_is_finite_and_bounded():
    k = kick()
    assert k.size > 0
    assert np.all(np.isfinite(k))
    assert np.max(np.abs(k)) <= 1.0


def test_snare_is_deterministic_for_a_given_seed():
    a = snare(np.random.default_rng(42))
    b = snare(np.random.default_rng(42))
    assert np.allclose(a, b)


def test_open_hat_is_longer_than_closed():
    assert hat(np.random.default_rng(0), open_=True).size > hat(np.random.default_rng(0)).size


def test_bass_and_lead_are_bounded():
    for sig in (pluck_bass(65.41, 0.4), soft_lead(261.63, 0.4)):
        assert np.all(np.isfinite(sig)) and np.max(np.abs(sig)) <= 1.0


def test_build_track_shape_and_range():
    buf = build_track(seconds=8, bpm=86, seed=1)
    assert buf.dtype == np.float32
    assert np.all(np.isfinite(buf))
    assert np.max(np.abs(buf)) <= 1.0
    assert SR * 6 < buf.size < SR * 12  # ~8 s plus guard


def test_build_track_is_reproducible():
    assert np.array_equal(build_track(8, 86, 7), build_track(8, 86, 7))


def test_seed_changes_the_melody():
    assert not np.array_equal(build_track(8, 86, 1), build_track(8, 86, 2))


def test_pad_is_finite_and_bounded():
    p = pad([261.63, 392.0], 0.5)
    assert p.size > 0
    assert np.all(np.isfinite(p))
    assert np.max(np.abs(p)) <= 1.0


def test_strings_is_finite_and_bounded():
    s = strings([261.63, 329.63, 392.0], 0.5)
    assert s.size > 0
    assert np.all(np.isfinite(s))
    assert np.max(np.abs(s)) <= 1.0


def test_synth_lead_is_finite_and_bounded():
    sl = synth_lead(523.25, 0.5)
    assert sl.size > 0
    assert np.all(np.isfinite(sl))
    assert np.max(np.abs(sl)) <= 1.0


@pytest.mark.parametrize(
    "make_sig",
    [
        lambda rng: transition_rise(rng, 0.5),
        lambda rng: transition_fill(rng, 0.5),
        lambda rng: transition_drop(rng, 0.5),
        lambda rng: transition_halt(rng, 0.5),
    ],
)
def test_transitions_are_finite_and_bounded(make_sig):
    rng = np.random.default_rng(123)
    sig = make_sig(rng)
    assert sig.size > 0
    assert np.all(np.isfinite(sig))
    assert np.max(np.abs(sig)) <= 1.0


def test_build_track_reports_progress():
    calls: list[tuple[int, int]] = []
    build_track(seconds=8, bpm=120, seed=1, progress=lambda d, t: calls.append((d, t)))
    assert calls
    assert all(0 <= done <= total for done, total in calls)
    assert calls[-1][0] == calls[-1][1]
    assert calls[-1][1] > 0


def test_build_track_progress_ignores_none_callback():
    # Determinism must remain intact with progress=None (default).
    sig = build_track(seconds=8, bpm=120, seed=7)
    assert sig.size > 0
