"""Genre presets — bundle chord mode + bass + instrument + key-awareness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Genre:
    name: str
    chord_mode: str            # "Diatonic triad", "Diatonic 7th", or a CHORD_RECIPES key
    bass_octaves: int          # 0 = no bass; 1 = root one octave down
    dom7_on_V: bool            # upgrade V chord to V7
    instrument_program: int    # GM program 0..127
    blurb: str                 # one-line description shown in UI tooltip


GENRES: list[Genre] = [
    Genre(
        name="Pop",
        chord_mode="Diatonic triad",
        bass_octaves=0,
        dom7_on_V=False,
        instrument_program=1,  # Bright Piano
        blurb="Diatonic triads, no bass — light, bright pop sound.",
    ),
    Genre(
        name="Jazz",
        chord_mode="Diatonic 7th",
        bass_octaves=1,
        dom7_on_V=True,
        instrument_program=4,  # Electric Piano (Rhodes)
        blurb="7ths everywhere + Rhodes + root bass. V is V7.",
    ),
    Genre(
        name="Classical",
        chord_mode="Diatonic triad",
        bass_octaves=1,
        dom7_on_V=False,
        instrument_program=0,  # Acoustic Grand Piano
        blurb="Triads, octave-bass, Acoustic Grand. Tonal & clean.",
    ),
    Genre(
        name="Beatles",
        chord_mode="Diatonic triad",
        bass_octaves=0,
        dom7_on_V=True,
        instrument_program=0,  # Acoustic Grand Piano
        blurb="Triads + V7 cadence flavour — classic 60s pop progressions.",
    ),
    Genre(
        name="Custom",
        chord_mode="",
        bass_octaves=0,
        dom7_on_V=False,
        instrument_program=0,
        blurb="No preset — change Instrument / Chord / Key by hand.",
    ),
]


def get_genre(name: str) -> Genre | None:
    for g in GENRES:
        if g.name == name:
            return g
    return None
