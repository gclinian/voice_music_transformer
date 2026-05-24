# voice-to-piano

[![CI](https://github.com/gclinian/voice_music_transformer/actions/workflows/ci.yml/badge.svg)](https://github.com/gclinian/voice_music_transformer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Made with PySide6](https://img.shields.io/badge/GUI-PySide6-41cd52.svg)](https://wiki.qt.io/Qt_for_Python)

**Sing into a microphone, hear a piano — or a violin, cello, or flute. Choose a genre, and the app auto-generates chords in your key. Save your performance as WAV, MIDI, and printable sheet music.**

> Two-pass workflow: record a clean single-line melody, then click **Harmonize** and the app reads the whole phrase, detects the key, and writes a chord track underneath your melody.

---

## Features

- 🎤 **Real-time pitch detection** — FFT autocorrelation with parabolic interpolation. Sub-cent accuracy on clean tones, ~50 ms latency end-to-end.
- 🎹 **18 General MIDI instruments** — Acoustic & Electric Piano, Violin, Viola, Cello, String Ensemble, Flute, Trumpet, Vibraphone, Choir, Square Lead, and more. Switch live.
- 🎼 **Key-aware chords** — pick from 24 keys (12 major + 12 minor); `Diatonic triad` / `Diatonic 7th` modes pick the right quality (Dm, not D, when you sing D in C major). 11 other shapes for power chords, sus4s, parallel triads, etc.
- 🎚 **Genre presets** — Pop / Jazz / Classical / Beatles / Custom. One click sets Instrument + Chord + Rhythm pattern + BPM + Bass + V7 to a coherent voicing.
- 🥁 **Rhythm patterns** — 8 voicing styles (Block, Arpeggio Up/Down, Alberti bass, Pop 1+3, Waltz, Jazz comp, Strum) at any BPM. Pop's root-on-1+3 backbeat sounds nothing like Classical's Alberti 16ths, even with the same chord.
- 🎙 **Three-file recording** — WAV (stereo 44.1 kHz), MIDI (note events), and **MusicXML** (printable sheet music, opens in MuseScore / Finale / Sibelius).
- ♪ **Post-hoc harmonization** — record melody alone, then let the app analyse the whole phrase to add context-aware chords (V→I cadences, ii→V approaches, downbeat alignment).
- 🖥 **Native GUI** — PySide6 / Qt 6. 88-key keyboard widget with highlighted active chord, VU meter, threshold/confidence sliders.

## Demo

A quick what-it-does cheat sheet:

| You sing | Chord = Off (mono) | Chord = Diatonic, Key = C major | Chord = Diatonic 7th |
|---|---|---|---|
| C | C | **C E G** (I) | **C E G B** (Imaj7) |
| D | D | **D F A** (ii — Dm) | **D F A C** (ii7 — Dm7) |
| G | G | **G B D** (V) | **G B D F** (V7) |

…with Bass octaves on, each chord also adds the root one octave below.

## Quickstart

### macOS

```sh
# 1. System dependency
brew install fluid-synth

# 2. Clone + sync (uv handles the Python 3.11 venv)
git clone https://github.com/gclinian/voice_music_transformer.git
cd voice_music_transformer
uv sync

# 3. Free SoundFont (~31 MB, GeneralUser GS)
./scripts/download_soundfont.sh

# 4. Run
uv run python main.py
```

### Linux

```sh
sudo apt install fluidsynth libportaudio2     # or: dnf install fluidsynth portaudio
git clone https://github.com/gclinian/voice_music_transformer.git
cd voice_music_transformer
uv sync
./scripts/download_soundfont.sh
uv run python main.py
```

### Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) ≥ 0.4
- [FluidSynth](https://www.fluidsynth.org/) ≥ 2.0
- A microphone

## Usage

1. Launch the app.
2. (Optional) Pick a **Genre** — Pop, Jazz, Classical, Beatles. This sets sensible defaults for everything below.
3. Choose your **Key** if you know it. Otherwise leave it on `C major` and use Harmonize later (which auto-detects).
4. Pick an **Instrument** — Acoustic Grand, Violin, Cello, Flute, etc.
5. Hit **Start** to open the mic. Hit **● Record** to capture.
6. Sing, hum, or whistle. The highlighted keyboard shows what's playing; the VU meter shows your level.
7. **■ Stop Recording** writes three files to `recordings/`:
   - `piano_<timestamp>.wav` — audio of the synthesised performance
   - `piano_<timestamp>.mid` — MIDI you can drop into a DAW
   - `piano_<timestamp>.musicxml` — sheet music for MuseScore
8. **♪ Harmonize Last** (recommended after a melody-only recording): the app reads the just-saved MIDI, detects the key, picks one chord per bar with full-phrase context, and saves a `*_harmonized.{wav,mid,musicxml}` triple.

## How it works

```
┌──────────┐  44.1 kHz  ┌────────────────────────┐
│   Mic    │ ─────────▶ │   InputStream callback │
└──────────┘            └─────────────┬──────────┘
                                      │ 2048-sample blocks
                                      ▼
                           ┌─────────────────────┐
                           │ FFT autocorrelation │ ← Pitch detection
                           │   pitch detection   │   (voice_to_piano/pitch.py)
                           └──────────┬──────────┘
                                      │ MIDI note
                                      ▼
                       ┌────────────────────────────┐
                       │   Chord mode + Key + Bass  │ ← voice_to_piano/harmony.py
                       │  → note-on / note-off set  │   voice_to_piano/instruments.py
                       └──────────────┬─────────────┘
                                      │
              ┌───────────────────────┼───────────────────┐
              ▼                       ▼                   ▼
       ┌─────────────┐      ┌──────────────────┐  ┌─────────────┐
       │ FluidSynth  │      │   MIDI events    │  │  Recording  │
       │  get_samples│      │     buffer       │  │   buffer    │
       └──────┬──────┘      └────────┬─────────┘  └──────┬──────┘
              │                      │ stop_recording    │
              ▼                      ▼                   ▼
       ┌─────────────┐      ┌─────────────────┐  ┌──────────────┐
       │  Speakers   │      │ MIDI / MusicXML │  │     WAV      │
       └─────────────┘      └─────────────────┘  └──────────────┘
                                      │
                                      ▼
                             ♪  Harmonize  ♪
                       ┌────────────────────────────┐
                       │  music21 key detection +   │
                       │  per-bar chord scoring     │ ← voice_to_piano/harmonizer.py
                       │  with progression bonuses  │
                       └──────────────┬─────────────┘
                                      ▼
                       *_harmonized.{wav,mid,musicxml}
```

Two threads coordinate through Qt signals:

- **PortAudio's I/O callbacks** (input + output) push/pull samples in real time.
- A **worker thread** drains the input queue, runs pitch detection, decides what to play, and emits Qt signals that Qt queues to the UI thread automatically.

See `voice_to_piano/audio_engine.py` for the full state machine.

## Architecture

```
main.py                       Entry point: parse CLI args, launch QApplication.
voice_to_piano/
├── pitch.py                  FFT autocorrelation pitch detection.
├── harmony.py                Keys, scale degrees, diatonic chord lookup.
├── harmonizer.py             Post-hoc chord generation (whole-melody context).
├── instruments.py            GM instrument list + chord-recipe table.
├── genres.py                 Genre presets (Pop / Jazz / Classical / Beatles).
├── audio_engine.py           Mic → pitch → FluidSynth → speaker; recording.
├── render.py                 Offline MIDI → WAV using FluidSynth.
└── ui.py                     PySide6 MainWindow + custom keyboard/VU widgets.
tests/                        Pytest suite — pitch, harmony, genres.
scripts/download_soundfont.sh GeneralUser GS fetch helper.
```

## Roadmap

- [ ] True polyphonic pitch detection (basic-pitch) for multi-voice input
- [ ] Live arpeggiator / Alberti-bass patterns under the chord
- [ ] Tempo detection so harmonizer aligns chord changes to musical bars instead of fixed quarter-note windows
- [ ] In-app sheet-music preview (no need to open MuseScore externally)
- [ ] Cross-platform CI for macOS + Windows
- [ ] Better non-diatonic note handling (modal mixture, secondary dominants)

## Contributing

PRs and ideas are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup and house style. Bug reports and feature requests via [Issues](https://github.com/gclinian/voice_music_transformer/issues).

## License

[MIT](LICENSE). Includes piano samples from [GeneralUser GS](http://www.schristiancollins.com/generaluser.php) by S. Christian Collins, which has its own permissive license — the file is fetched at install time and is not redistributed by this repo.

## Acknowledgements

- [FluidSynth](https://www.fluidsynth.org/) — open-source SoundFont synthesizer
- [GeneralUser GS](http://www.schristiancollins.com/generaluser.php) — free GM SoundFont by S. Christian Collins
- [music21](https://web.mit.edu/music21/) (MIT) — music theory and MusicXML
- [Krumhansl & Schmuckler](https://en.wikipedia.org/wiki/Krumhansl%E2%80%93Schmuckler_key-finding_algorithm) — key-detection algorithm used by the harmonizer
- [PySide6 / Qt](https://wiki.qt.io/Qt_for_Python) — the GUI toolkit
