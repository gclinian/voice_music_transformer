"""Diatonic chord lookup tests."""

from __future__ import annotations

import pytest

from voice_to_piano.harmony import (
    KEYS,
    diatonic_chord_notes,
    key_label_to_tonic,
)
from voice_to_piano.pitch import midi_to_note_name


def chord_names(notes: list[int]) -> list[str]:
    return [midi_to_note_name(n) for n in notes]


def test_c_major_scale_triads() -> None:
    """Each scale degree gets the right quality triad in C major."""
    tonic, mode = key_label_to_tonic("C major")
    expected = {
        60: ["C4", "E4", "G4"],   # I
        62: ["D4", "F4", "A4"],   # ii (Dm — minor third!)
        64: ["E4", "G4", "B4"],   # iii (Em)
        65: ["F4", "A4", "C5"],   # IV
        67: ["G4", "B4", "D5"],   # V
        69: ["A4", "C5", "E5"],   # vi (Am)
        71: ["B4", "D5", "F5"],   # vii° (Bdim)
    }
    for root, want in expected.items():
        got = chord_names(diatonic_chord_notes(root, tonic, mode))
        assert got == want, f"sing {midi_to_note_name(root)} → {got} (want {want})"


def test_a_minor_natural_scale_triads() -> None:
    """A minor (natural): v is minor, not the harmonic-minor V."""
    tonic, mode = key_label_to_tonic("A minor")
    # v in A minor natural is Em, not E
    got = chord_names(diatonic_chord_notes(64, tonic, mode))
    assert got == ["E4", "G4", "B4"]
    # i is Am
    got = chord_names(diatonic_chord_notes(69, tonic, mode))
    assert got == ["A4", "C5", "E5"]


def test_dominant_7_on_V() -> None:
    """dom7_on_V flag upgrades V to a V7 with the minor seventh."""
    tonic, mode = key_label_to_tonic("C major")
    base = diatonic_chord_notes(67, tonic, mode)
    with_7 = diatonic_chord_notes(67, tonic, mode, dom7_on_V=True)
    assert chord_names(base) == ["G4", "B4", "D5"]
    assert chord_names(with_7) == ["G4", "B4", "D5", "F5"]


def test_bass_octaves_adds_lower_root() -> None:
    tonic, mode = key_label_to_tonic("C major")
    with_bass = diatonic_chord_notes(60, tonic, mode, bass_octaves=1)
    assert chord_names(with_bass) == ["C3", "C4", "E4", "G4"]


def test_seventh_chords_in_major() -> None:
    """V becomes V7 (dominant) automatically when use_seventh=True."""
    tonic, mode = key_label_to_tonic("C major")
    got = chord_names(diatonic_chord_notes(67, tonic, mode, use_seventh=True))
    assert got == ["G4", "B4", "D5", "F5"]  # G7
    got_ii7 = chord_names(diatonic_chord_notes(62, tonic, mode, use_seventh=True))
    assert got_ii7 == ["D4", "F4", "A4", "C5"]  # Dm7


def test_24_keys_available() -> None:
    assert len(KEYS) == 24


@pytest.mark.parametrize("label,tonic_pc,mode", KEYS)
def test_key_label_to_tonic_roundtrip(label: str, tonic_pc: int, mode: str) -> None:
    assert key_label_to_tonic(label) == (tonic_pc, mode)
