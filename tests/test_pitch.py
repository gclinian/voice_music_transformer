"""Pitch detection sanity checks against synthetic sines."""

from __future__ import annotations

import numpy as np
import pytest

from voice_to_piano.pitch import (
    detect_pitch_autocorr,
    freq_to_midi,
    midi_to_note_name,
)

SR = 44100


def sine(freq_hz: float, duration: float = 0.046) -> np.ndarray:
    """0.046s default ≈ 2048 samples at 44.1 kHz — the engine's analysis block."""
    n = int(SR * duration)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * freq_hz * t).astype(np.float32)


@pytest.mark.parametrize(
    "freq",
    [196.0, 220.0, 261.63, 329.63, 440.0, 523.25, 659.25, 880.0],
)
def test_detect_pitch_returns_close_to_input(freq: float) -> None:
    """Voice range: 200 Hz (G3) up to 880 Hz (A5) — covers most singing."""
    detected = detect_pitch_autocorr(sine(freq), SR)
    assert detected is not None
    # Allow 1% error — autocorrelation + parabolic interp is sub-cent on clean sines.
    assert abs(detected - freq) / freq < 0.01, f"{detected} vs {freq}"


def test_low_voice_works_with_longer_window() -> None:
    """A4-down to ~100Hz needs more than the default 46ms block — engine
    only commits to a chord after several frames, so this is fine in practice."""
    detected = detect_pitch_autocorr(sine(110.0, duration=0.2), SR)
    assert detected is not None
    assert abs(detected - 110.0) / 110.0 < 0.01


def test_detect_pitch_returns_none_on_silence() -> None:
    silence = np.zeros(2048, dtype=np.float32)
    assert detect_pitch_autocorr(silence, SR) is None


def test_detect_pitch_returns_none_below_min() -> None:
    detected = detect_pitch_autocorr(sine(40.0), SR, fmin=80.0)
    assert detected is None


@pytest.mark.parametrize(
    "freq,midi",
    [(440.0, 69), (261.626, 60), (130.813, 48), (1046.5, 84)],
)
def test_freq_to_midi_matches_standard_tuning(freq: float, midi: int) -> None:
    assert freq_to_midi(freq) == midi


def test_midi_to_note_name() -> None:
    assert midi_to_note_name(69) == "A4"
    assert midi_to_note_name(60) == "C4"
    assert midi_to_note_name(61) == "C#4"
    assert midi_to_note_name(21) == "A0"
    assert midi_to_note_name(108) == "C8"
