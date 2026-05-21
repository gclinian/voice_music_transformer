"""Offline MIDI -> WAV renderer using FluidSynth.

Used by the harmonizer flow to produce audio for an auto-generated chord
track, separate from the live engine.
"""

from __future__ import annotations

import os
import tempfile
import wave
from pathlib import Path

os.environ.setdefault("HOMEBREW_PREFIX", "/opt/homebrew")

import fluidsynth  # noqa: E402
import mido  # noqa: E402
import numpy as np  # noqa: E402

SAMPLE_RATE = 44100


def render_midi_to_wav(
    midi_path: str | Path,
    soundfont_path: str | Path,
    wav_path: str | Path,
    program: int = 0,
    tail_seconds: float = 1.5,
) -> None:
    """Render a MIDI file to a stereo 44.1 kHz int16 WAV."""
    fs = fluidsynth.Synth(samplerate=float(SAMPLE_RATE), gain=1.0)
    try:
        sfid = fs.sfload(str(soundfont_path))
        if sfid == -1:
            raise RuntimeError(f"FluidSynth could not load SoundFont: {soundfont_path}")
        fs.program_select(0, sfid, 0, program)

        mid = mido.MidiFile(str(midi_path))
        chunks: list[np.ndarray] = []

        for msg in mid:
            if msg.time > 0:
                n = int(round(msg.time * SAMPLE_RATE))
                if n > 0:
                    chunks.append(fs.get_samples(n))
            if msg.is_meta:
                continue
            if msg.type == "note_on" and msg.velocity > 0:
                fs.noteon(msg.channel, msg.note, msg.velocity)
            elif msg.type == "note_off" or (
                msg.type == "note_on" and msg.velocity == 0
            ):
                fs.noteoff(msg.channel, msg.note)
            elif msg.type == "program_change":
                fs.program_change(msg.channel, msg.program)

        tail = int(SAMPLE_RATE * tail_seconds)
        if tail > 0:
            chunks.append(fs.get_samples(tail))
    finally:
        fs.delete()

    if not chunks:
        return
    data = np.concatenate(chunks)
    with wave.open(str(wav_path), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(data.tobytes())


def render_score_to_wav(
    score,  # music21.stream.Score
    soundfont_path: str | Path,
    wav_path: str | Path,
    program: int = 0,
    tail_seconds: float = 1.5,
) -> None:
    """Render a music21 Score to WAV via a temporary MIDI file."""
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as tmp:
        midi_tmp = tmp.name
    try:
        score.write("midi", fp=midi_tmp)
        render_midi_to_wav(midi_tmp, soundfont_path, wav_path, program, tail_seconds)
    finally:
        try:
            os.unlink(midi_tmp)
        except OSError:
            pass
