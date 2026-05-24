"""Pattern definitions + voice resolver tests."""

from __future__ import annotations

import pytest

from voice_to_piano.patterns import PATTERNS, resolve_voices

CHORD = [48, 60, 64, 67]  # C2, C4, E4, G4


def test_pattern_library_includes_expected_names() -> None:
    expected = {
        "Block",
        "Arpeggio Up",
        "Arpeggio Down",
        "Alberti bass",
        "Pop 1+3",
        "Waltz (3/4)",
        "Jazz comp",
        "Strum",
    }
    assert expected.issubset(PATTERNS.keys())


def test_every_pattern_event_offset_within_length() -> None:
    for pat in PATTERNS.values():
        for ev in pat.events:
            assert 0.0 <= ev.offset_beats < pat.length_beats + 1e-6, (
                f"{pat.name}: event at {ev.offset_beats} but length {pat.length_beats}"
            )


@pytest.mark.parametrize(
    "spec,expected",
    [
        ("all",   [48, 60, 64, 67]),
        ("upper", [60, 64, 67]),
        ("root",  [48]),
        ("low",   [48]),
        ("high",  [67]),
        (0,       [48]),
        (1,       [60]),
        (2,       [64]),
        (3,       [67]),
        (-1,      [67]),
        (-2,      [64]),
        # Out of range clips to nearest end.
        (10,      [67]),
        (-99,     [48]),
    ],
)
def test_resolve_voices(spec, expected) -> None:
    assert resolve_voices(spec, CHORD) == expected


def test_resolve_voices_empty_chord() -> None:
    assert resolve_voices("all", []) == []
    assert resolve_voices("root", []) == []
    assert resolve_voices(0, []) == []


def test_resolve_voices_single_note_chord() -> None:
    """A 1-note chord falls through cleanly — 'upper' returns the same note."""
    assert resolve_voices("upper", [60]) == [60]
    assert resolve_voices("root", [60]) == [60]
    assert resolve_voices("high", [60]) == [60]


def test_pop_and_classical_patterns_differ_audibly() -> None:
    """Pop fires once per beat, Alberti fires four 16ths per beat — events/beat must differ."""
    pop = PATTERNS["Pop 1+3"]
    alberti = PATTERNS["Alberti bass"]
    pop_events_per_beat = len(pop.events) / pop.length_beats
    alberti_events_per_beat = len(alberti.events) / alberti.length_beats
    assert alberti_events_per_beat > pop_events_per_beat * 2
