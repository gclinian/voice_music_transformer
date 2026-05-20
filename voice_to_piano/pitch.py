"""Pitch detection. FFT-based autocorrelation — fast, works well for voice."""

from __future__ import annotations

import numpy as np

MIN_FREQ = 70.0
MAX_FREQ = 1100.0


def freq_to_midi(freq: float) -> int:
    return int(round(69 + 12 * np.log2(freq / 440.0)))


_NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def midi_to_note_name(midi: int) -> str:
    return f"{_NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def detect_pitch_autocorr(
    frame: np.ndarray,
    sr: int,
    fmin: float = MIN_FREQ,
    fmax: float = MAX_FREQ,
    confidence: float = 0.3,
) -> float | None:
    """FFT-based autocorrelation pitch detection. Returns freq in Hz or None."""
    n = len(frame)
    frame = frame - frame.mean()
    if np.max(np.abs(frame)) < 1e-6:
        return None

    nfft = 1 << ((2 * n - 1).bit_length())
    spectrum = np.fft.rfft(frame, n=nfft)
    acf = np.fft.irfft(spectrum * np.conj(spectrum))[:n]

    tau_min = int(sr / fmax)
    tau_max = min(int(sr / fmin), n - 1)
    if tau_max <= tau_min + 1:
        return None

    region = acf[tau_min : tau_max + 1]
    peak = int(np.argmax(region)) + tau_min
    if acf[0] <= 0 or acf[peak] < confidence * acf[0]:
        return None

    if 0 < peak < len(acf) - 1:
        a, b, c = acf[peak - 1], acf[peak], acf[peak + 1]
        denom = a - 2 * b + c
        offset = 0.5 * (a - c) / denom if denom != 0 else 0.0
        tau_est = peak + offset
    else:
        tau_est = float(peak)

    return sr / tau_est if tau_est > 0 else None
