"""Key signatures and diatonic chord lookup."""

from __future__ import annotations

PITCH_CLASS_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

# (display label, tonic pitch-class, mode)
KEYS: list[tuple[str, int, str]] = [
    ("C major", 0, "major"),
    ("G major", 7, "major"),
    ("D major", 2, "major"),
    ("A major", 9, "major"),
    ("E major", 4, "major"),
    ("B major", 11, "major"),
    ("F major", 5, "major"),
    ("Bb major", 10, "major"),
    ("Eb major", 3, "major"),
    ("Ab major", 8, "major"),
    ("Db major", 1, "major"),
    ("Gb major", 6, "major"),
    ("A minor", 9, "minor"),
    ("E minor", 4, "minor"),
    ("B minor", 11, "minor"),
    ("F# minor", 6, "minor"),
    ("C# minor", 1, "minor"),
    ("D minor", 2, "minor"),
    ("G minor", 7, "minor"),
    ("C minor", 0, "minor"),
    ("F minor", 5, "minor"),
    ("Bb minor", 10, "minor"),
    ("Eb minor", 3, "minor"),
    ("Ab minor", 8, "minor"),
]

# Quality -> semitone intervals over the root
QUALITY_INTERVALS: dict[str, tuple[int, ...]] = {
    "maj":  (0, 4, 7),
    "min":  (0, 3, 7),
    "dim":  (0, 3, 6),
    "aug":  (0, 4, 8),
    "maj7": (0, 4, 7, 11),
    "min7": (0, 3, 7, 10),
    "dom7": (0, 4, 7, 10),
    "dim7": (0, 3, 6, 9),
    "m7b5": (0, 3, 6, 10),
}

# Scale-degree (semitones above tonic) -> chord quality
# Triads
_MAJOR_TRI = {0: "maj", 2: "min", 4: "min", 5: "maj", 7: "maj", 9: "min", 11: "dim"}
_MINOR_TRI = {0: "min", 2: "dim", 3: "maj", 5: "min", 7: "min", 8: "maj", 10: "maj"}
# 7ths
_MAJOR_7 = {0: "maj7", 2: "min7", 4: "min7", 5: "maj7", 7: "dom7", 9: "min7", 11: "m7b5"}
_MINOR_7 = {0: "min7", 2: "m7b5", 3: "maj7", 5: "min7", 7: "min7", 8: "maj7", 10: "dom7"}


def diatonic_chord_notes(
    root_midi: int,
    key_tonic_pc: int,
    key_mode: str,
    use_seventh: bool = False,
    bass_octaves: int = 0,
    dom7_on_V: bool = False,
) -> list[int]:
    """Return the MIDI notes for the diatonic chord rooted at `root_midi`.

    `key_mode` is "major" or "minor". For pitch classes outside the diatonic
    set we fall back to a triad of the parallel quality (major in major key,
    minor in minor key) so chromatic notes still produce something musical.

    `bass_octaves`>0 adds the root that many octaves lower (e.g., 1 -> piano
    left-hand bass).
    `dom7_on_V` upgrades the V chord to a dominant 7th (Beatles cadence trick).
    """
    pc = root_midi % 12
    degree = (pc - key_tonic_pc) % 12

    if key_mode == "major":
        table = _MAJOR_7 if use_seventh else _MAJOR_TRI
        fallback = "maj7" if use_seventh else "maj"
    else:
        table = _MINOR_7 if use_seventh else _MINOR_TRI
        fallback = "min7" if use_seventh else "min"

    quality = table.get(degree, fallback)
    if dom7_on_V and key_mode == "major" and degree == 7:
        quality = "dom7"
    if dom7_on_V and key_mode == "minor" and degree == 7:
        quality = "dom7"  # V in minor borrowed from harmonic minor

    notes = [root_midi + i for i in QUALITY_INTERVALS[quality]]
    for k in range(1, bass_octaves + 1):
        notes.insert(0, root_midi - 12 * k)
    return notes


def key_label_to_tonic(label: str) -> tuple[int, str]:
    """'C major' -> (0, 'major'). Returns (0, 'major') for unknown labels."""
    for name, tonic, mode in KEYS:
        if name == label:
            return tonic, mode
    return 0, "major"
