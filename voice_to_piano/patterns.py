"""Rhythm patterns. Each pattern describes WHEN and WHICH voice plays.

A pattern is a loop of events. Each event says: at offset T into the loop,
play `voice` for `duration` beats with `velocity_mult` * base velocity.

`voice` resolves against the current chord (sorted ascending, root first):
  int n      -> chord[n] (clipped to range)
  -1, -2     -> count from top (highest = -1)
  "root"     -> lowest note
  "high"     -> highest note
  "all"      -> every voice in the chord (block hit)
  "upper"    -> every voice except the lowest (treble stab)

Block is the special pattern that plays everything at once and sustains —
this is the original behaviour, handled inline in the engine.
"""

from __future__ import annotations

from dataclasses import dataclass

VoiceSpec = int | str


@dataclass(frozen=True)
class PatternEvent:
    offset_beats: float
    voice: VoiceSpec
    duration_beats: float = 0.45
    velocity_mult: float = 1.0


@dataclass(frozen=True)
class RhythmPattern:
    name: str
    length_beats: float
    events: tuple[PatternEvent, ...]
    blurb: str = ""


# --- pattern library ---------------------------------------------------------

_BLOCK = RhythmPattern(
    name="Block",
    length_beats=4.0,
    events=(PatternEvent(0.0, "all", 4.0, 1.0),),
    blurb="All voices at once, sustained (original behaviour).",
)

_ARP_UP = RhythmPattern(
    name="Arpeggio Up",
    length_beats=2.0,
    events=(
        PatternEvent(0.0, 0, 0.45, 0.95),
        PatternEvent(0.5, 1, 0.45, 0.90),
        PatternEvent(1.0, 2, 0.45, 0.90),
        PatternEvent(1.5, -1, 0.45, 0.95),
    ),
    blurb="Eighth-note arpeggio bottom-to-top.",
)

_ARP_DOWN = RhythmPattern(
    name="Arpeggio Down",
    length_beats=2.0,
    events=(
        PatternEvent(0.0, -1, 0.45, 0.95),
        PatternEvent(0.5, 2, 0.45, 0.90),
        PatternEvent(1.0, 1, 0.45, 0.90),
        PatternEvent(1.5, 0, 0.45, 0.95),
    ),
    blurb="Eighth-note arpeggio top-to-bottom.",
)

_ALBERTI = RhythmPattern(
    name="Alberti bass",
    length_beats=1.0,
    events=(
        PatternEvent(0.00, 0, 0.22, 0.95),
        PatternEvent(0.25, -1, 0.22, 0.80),
        PatternEvent(0.50, 1, 0.22, 0.88),
        PatternEvent(0.75, -1, 0.22, 0.80),
    ),
    blurb="Classical low-high-mid-high 16ths (Mozart left-hand staple).",
)

_POP = RhythmPattern(
    name="Pop 1+3",
    length_beats=4.0,
    events=(
        PatternEvent(0.0, "root", 0.45, 1.0),
        PatternEvent(1.0, "upper", 0.45, 0.85),
        PatternEvent(2.0, "root", 0.45, 1.0),
        PatternEvent(3.0, "upper", 0.45, 0.85),
    ),
    blurb="Root on beats 1+3, upper voices on 2+4. Classic backbeat feel.",
)

_WALTZ = RhythmPattern(
    name="Waltz (3/4)",
    length_beats=3.0,
    events=(
        PatternEvent(0.0, "root", 0.9, 1.0),
        PatternEvent(1.0, "upper", 0.9, 0.80),
        PatternEvent(2.0, "upper", 0.9, 0.80),
    ),
    blurb="One bar of 3: root, chord, chord.",
)

_JAZZ = RhythmPattern(
    name="Jazz comp",
    length_beats=2.0,
    events=(
        PatternEvent(0.50, "all", 0.4, 0.85),
        PatternEvent(1.50, "all", 0.4, 0.85),
    ),
    blurb="Offbeat stabs on the 'and' of 1 and 'and' of 2. Sparse, sits behind soloist.",
)

_STRUM = RhythmPattern(
    name="Strum",
    length_beats=4.0,
    events=(
        # Quick low-to-high roll, then leave the chord ringing for the bar.
        PatternEvent(0.00, 0, 0.06, 0.7),
        PatternEvent(0.06, 1, 0.06, 0.8),
        PatternEvent(0.12, 2, 0.06, 0.9),
        PatternEvent(0.18, -1, 3.6, 0.95),
    ),
    blurb="One quick low-to-high roll per bar, then let the chord ring.",
)


PATTERNS: dict[str, RhythmPattern] = {
    p.name: p
    for p in (_BLOCK, _ARP_UP, _ARP_DOWN, _ALBERTI, _POP, _WALTZ, _JAZZ, _STRUM)
}

DEFAULT_PATTERN = "Block"
DEFAULT_BPM = 96


def resolve_voices(spec: VoiceSpec, chord: list[int]) -> list[int]:
    """Return the MIDI notes a pattern event should play, given the chord."""
    if not chord:
        return []
    if spec == "all":
        return list(chord)
    if spec == "upper":
        return list(chord[1:]) if len(chord) > 1 else [chord[0]]
    if spec == "root" or spec == "low":
        return [chord[0]]
    if spec == "high":
        return [chord[-1]]
    if isinstance(spec, int):
        idx = max(0, len(chord) + spec) if spec < 0 else min(spec, len(chord) - 1)
        return [chord[idx]]
    return []
