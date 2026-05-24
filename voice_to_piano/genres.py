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
    pattern: str               # PATTERNS key — rhythm style
    bpm: int                   # tempo for the pattern player
    blurb: str                 # one-line description shown in UI tooltip


GENRES: list[Genre] = [
    Genre(
        name="Pop",
        chord_mode="Diatonic triad",
        bass_octaves=0,
        dom7_on_V=False,
        instrument_program=1,  # Bright Piano
        pattern="Pop 1+3",
        bpm=100,
        blurb="Diatonic triads, root-on-1+3 backbeat, Bright Piano.",
    ),
    Genre(
        name="Jazz",
        chord_mode="Diatonic 7th",
        bass_octaves=1,
        dom7_on_V=True,
        instrument_program=4,  # Electric Piano (Rhodes)
        pattern="Jazz comp",
        bpm=132,
        blurb="7ths everywhere, Rhodes, offbeat stabs. V is V7.",
    ),
    Genre(
        name="Classical",
        chord_mode="Diatonic triad",
        bass_octaves=1,
        dom7_on_V=False,
        instrument_program=0,  # Acoustic Grand Piano
        pattern="Alberti bass",
        bpm=96,
        blurb="Triads, octave bass, Alberti 16ths — Mozart-style accompaniment.",
    ),
    Genre(
        name="Beatles",
        chord_mode="Diatonic triad",
        bass_octaves=0,
        dom7_on_V=True,
        instrument_program=0,  # Acoustic Grand Piano
        pattern="Strum",
        bpm=112,
        blurb="Strummed triads + V7 cadences — 60s pop / folk feel.",
    ),
    Genre(
        name="Custom",
        chord_mode="",
        bass_octaves=0,
        dom7_on_V=False,
        instrument_program=0,
        pattern="",  # don't override
        bpm=0,       # don't override
        blurb="No preset — change Instrument / Chord / Key / Pattern by hand.",
    ),
]


def get_genre(name: str) -> Genre | None:
    for g in GENRES:
        if g.name == name:
            return g
    return None
