"""Post-hoc chord generation: melody MIDI in -> melody + chord Score out.

Pipeline:
  1. Detect key from the whole melody (music21's Krumhansl-Schmuckler).
  2. Segment the melody into chord windows (default: one chord per measure).
  3. For each window, pick the diatonic chord that best fits the notes —
     score = notes-in-chord weight + bonus for strong functional progressions
     (V->I, IV->V, ii->V) relative to the previous chord.
  4. Return a music21 Score with the melody on top, chord track below, plus
     the detected Key signature.

Output is musical, not just acoustic: each chord lasts one window and the
chord choice respects the whole phrase, not just the note under it.
"""

from __future__ import annotations

from dataclasses import dataclass

import music21

# Diatonic triad templates: (degree in semitones from tonic, quality)
_MAJOR_TRIADS = [
    (0, "maj"),    # I
    (2, "min"),    # ii
    (4, "min"),    # iii
    (5, "maj"),    # IV
    (7, "maj"),    # V
    (9, "min"),    # vi
    (11, "dim"),   # vii°
]
_MINOR_TRIADS = [
    (0, "min"),    # i
    (2, "dim"),    # ii°
    (3, "maj"),    # III
    (5, "min"),    # iv
    (7, "min"),    # v
    (8, "maj"),    # VI
    (10, "maj"),   # VII
]
_QUALITY_INTERVALS = {
    "maj": (0, 4, 7),
    "min": (0, 3, 7),
    "dim": (0, 3, 6),
}
# Functional bonuses on (prev_degree, this_degree) — encourages V->I etc.
_PROGRESSION_BONUS_MAJOR = {
    (7, 0): 1.5,   # V -> I (authentic cadence)
    (5, 7): 1.0,   # IV -> V
    (2, 7): 1.0,   # ii -> V
    (9, 5): 0.7,   # vi -> IV
    (0, 5): 0.5,   # I -> IV
    (0, 7): 0.5,   # I -> V
}


@dataclass
class HarmonizeResult:
    score: music21.stream.Score
    detected_key: music21.key.Key
    progression: list[str]  # roman-ish labels per window for status display


def _chord_pcs(tonic_pc: int, degree: int, quality: str) -> set[int]:
    root_pc = (tonic_pc + degree) % 12
    return {(root_pc + i) % 12 for i in _QUALITY_INTERVALS[quality]}


def _chord_label(degree: int, quality: str, mode: str) -> str:
    roman_major = {0: "I", 2: "ii", 4: "iii", 5: "IV", 7: "V", 9: "vi", 11: "vii°"}
    roman_minor = {0: "i", 2: "ii°", 3: "III", 5: "iv", 7: "v", 8: "VI", 10: "VII"}
    table = roman_major if mode == "major" else roman_minor
    return table.get(degree, "?")


def _build_chord_notes(tonic_pc: int, degree: int, quality: str, octave: int = 3) -> list[int]:
    """Return MIDI numbers for the chord, voiced from a given octave."""
    root_pc = (tonic_pc + degree) % 12
    base = (octave + 1) * 12 + root_pc  # MIDI: C-1 = 0, so C(octave=3) = 48
    return [base + i for i in _QUALITY_INTERVALS[quality]]


def _segment_melody(
    notes: list[music21.note.Note], window_ql: float
) -> list[tuple[float, list[music21.note.Note]]]:
    """Group melody notes into windows of `window_ql` quarter-lengths each."""
    if not notes:
        return []
    end = max(n.offset + float(n.quarterLength) for n in notes)
    n_windows = max(1, int((end + window_ql - 1e-6) // window_ql) + (0 if (end % window_ql == 0) else 1))
    segments: list[tuple[float, list[music21.note.Note]]] = []
    for w in range(n_windows):
        start = w * window_ql
        stop = start + window_ql
        in_window = [
            n for n in notes
            if n.offset < stop and n.offset + float(n.quarterLength) > start
        ]
        if in_window:
            segments.append((start, in_window))
    return segments


def _score_chord(
    chord_pcs_set: set[int],
    seg_notes: list[music21.note.Note],
    window_start: float,
    window_ql: float,
    prev_degree: int | None,
    this_degree: int,
    prog_bonus_table: dict[tuple[int, int], float],
) -> float:
    score = 0.0
    for n in seg_notes:
        if n.pitch.pitchClass in chord_pcs_set:
            # Notes that overlap the window get scored by how much they overlap.
            n_start = max(n.offset, window_start)
            n_end = min(n.offset + float(n.quarterLength), window_start + window_ql)
            overlap = max(0.0, n_end - n_start)
            # Beat-1 notes weigh more (downbeat alignment matters harmonically).
            beat_bonus = 0.8 if abs(n.offset - window_start) < 0.05 else 0.0
            score += overlap + beat_bonus
    if prev_degree is not None:
        score += prog_bonus_table.get((prev_degree, this_degree), 0.0)
    return score


def harmonize_melody(
    midi_path: str,
    window_ql: float = 2.0,  # one chord per half-note
    chord_octave: int = 3,
) -> HarmonizeResult:
    """Read a melody MIDI, detect key, generate chord track, return Score."""
    src = music21.converter.parse(midi_path)
    detected_key = src.analyze("key")
    tonic_pc = detected_key.tonic.pitchClass
    mode = "major" if detected_key.mode == "major" else "minor"
    triads = _MAJOR_TRIADS if mode == "major" else _MINOR_TRIADS

    flat = src.flatten()
    melody_notes = sorted(
        flat.getElementsByClass(music21.note.Note),
        key=lambda n: n.offset,
    )
    segments = _segment_melody(melody_notes, window_ql)

    # Pick a chord per segment using context-aware scoring.
    progression: list[tuple[float, int, str, list[int]]] = []
    prev_degree: int | None = None
    for start, seg_notes in segments:
        best = None
        for degree, quality in triads:
            pcs = _chord_pcs(tonic_pc, degree, quality)
            s = _score_chord(
                pcs, seg_notes, start, window_ql, prev_degree, degree,
                _PROGRESSION_BONUS_MAJOR,
            )
            if best is None or s > best[0]:
                best = (s, degree, quality, _build_chord_notes(tonic_pc, degree, quality, chord_octave))
        assert best is not None
        progression.append((start, best[1], best[2], best[3]))
        prev_degree = best[1]

    # Last-chord cadence: nudge final chord toward I (or i in minor) if the
    # melody's last note is the tonic — sounds resolved.
    if progression and melody_notes:
        last_note_pc = melody_notes[-1].pitch.pitchClass
        if last_note_pc == tonic_pc:
            degree = 0
            quality = "maj" if mode == "major" else "min"
            start = progression[-1][0]
            progression[-1] = (
                start, degree, quality, _build_chord_notes(tonic_pc, degree, quality, chord_octave),
            )

    # Build output score: melody on top, chords below, with key signature.
    out = music21.stream.Score()
    melody_part = music21.stream.Part()
    melody_part.id = "melody"
    melody_part.partName = "Melody"
    melody_part.append(music21.instrument.Vocalist())
    melody_part.append(music21.key.Key(detected_key.tonic.name, mode))
    for n in melody_notes:
        melody_part.insert(n.offset, music21.note.Note(n.pitch, quarterLength=n.quarterLength))

    chord_part = music21.stream.Part()
    chord_part.id = "chords"
    chord_part.partName = "Chords"
    chord_part.append(music21.instrument.Piano())
    chord_part.append(music21.key.Key(detected_key.tonic.name, mode))
    labels: list[str] = []
    for start, degree, quality, notes in progression:
        c = music21.chord.Chord(notes, quarterLength=window_ql)
        chord_part.insert(start, c)
        labels.append(_chord_label(degree, quality, mode))

    out.insert(0, melody_part)
    out.insert(0, chord_part)
    return HarmonizeResult(score=out, detected_key=detected_key, progression=labels)
