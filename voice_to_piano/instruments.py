"""GM instrument list + chord interval recipes."""

from __future__ import annotations

# (display label, GM program number 0-127)
# Bank 0 in GeneralUser.sf2 holds all 128 standard General MIDI presets.
INSTRUMENTS: list[tuple[str, int]] = [
    ("Acoustic Grand Piano", 0),
    ("Bright Piano", 1),
    ("Electric Piano (Rhodes)", 4),
    ("Harpsichord", 6),
    ("Vibraphone", 11),
    ("Church Organ", 19),
    ("Nylon Guitar", 24),
    ("Acoustic Bass", 32),
    ("Violin", 40),
    ("Viola", 41),
    ("Cello", 42),
    ("String Ensemble", 48),
    ("Choir Aahs", 52),
    ("Trumpet", 56),
    ("Alto Sax", 65),
    ("Flute", 73),
    ("Square Lead", 80),
    ("New Age Pad", 88),
]


# Intervals (in semitones) added to the detected note when playing the chord.
# 0 = the detected note itself.
# "Diatonic triad" / "Diatonic 7th" are handled by harmony.py instead — the
# engine looks at the active Key and picks chord quality per scale degree.
CHORD_RECIPES: dict[str, tuple[int, ...]] = {
    "Off (mono)": (0,),
    "Diatonic triad": (),       # uses harmony.diatonic_chord_notes()
    "Diatonic 7th": (),         # uses harmony.diatonic_chord_notes(use_seventh=True)
    "Octave (root + 8va)": (0, 12),
    "Octave (root + 8vb)": (-12, 0),
    "Power (1+5)": (0, 7),
    "Major triad": (0, 4, 7),
    "Minor triad": (0, 3, 7),
    "Sus4": (0, 5, 7),
    "Major 7": (0, 4, 7, 11),
    "Minor 7": (0, 3, 7, 10),
    "Bass + Major triad": (-12, 0, 4, 7),
    "Bass + Minor triad": (-12, 0, 3, 7),
}

DIATONIC_MODES = {"Diatonic triad", "Diatonic 7th"}

DEFAULT_INSTRUMENT_PROGRAM = 0
DEFAULT_CHORD = "Diatonic triad"
DEFAULT_KEY = "C major"
