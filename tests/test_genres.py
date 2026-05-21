"""Genre preset sanity."""

from __future__ import annotations

from voice_to_piano.genres import GENRES, get_genre
from voice_to_piano.instruments import CHORD_RECIPES


def test_all_genres_have_valid_chord_modes() -> None:
    """Every preset's chord_mode is either empty (Custom) or in CHORD_RECIPES."""
    for g in GENRES:
        if g.chord_mode:
            assert g.chord_mode in CHORD_RECIPES, f"{g.name}: {g.chord_mode}"


def test_each_genre_has_unique_name() -> None:
    names = [g.name for g in GENRES]
    assert len(names) == len(set(names))


def test_get_genre_lookup() -> None:
    pop = get_genre("Pop")
    assert pop is not None
    assert pop.chord_mode == "Diatonic triad"
    assert get_genre("Nonexistent") is None


def test_jazz_uses_diatonic_7th() -> None:
    jazz = get_genre("Jazz")
    assert jazz is not None
    assert jazz.chord_mode == "Diatonic 7th"
    assert jazz.dom7_on_V is True
    assert jazz.bass_octaves >= 1
