# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Rhythm patterns** (`voice_to_piano/patterns.py`): 8 patterns that loop
  while a chord is held — Block, Arpeggio Up/Down, Alberti bass, Pop 1+3,
  Waltz, Jazz comp, Strum. Each defines event offsets, which chord voice
  to play, duration, and velocity multiplier.
- **Pattern player thread** in `AudioEngine` schedules note-on / note-off
  in sync with `bpm`; restarts on chord changes; tracks pending releases
  in a heap so overlapping voices don't leak.
- **Pattern + BPM controls** in the GUI (combo + 40–200 slider) with
  tooltips describing each pattern. Genres now set their own pattern + BPM
  (Pop → Pop 1+3 @ 100, Jazz → Jazz comp @ 132, Classical → Alberti @ 96,
  Beatles → Strum @ 112) so Pop and Beatles finally sound different.
- 20 new tests covering pattern data integrity, voice resolution, and
  genre/pattern coverage. Totals 70 tests, ~0.08 s.

## [0.2.0] - 2026-05-21

### Added
- **Post-hoc harmonizer** (`voice_to_piano/harmonizer.py`): records melody-only, then
  detects key via Krumhansl-Schmuckler and picks chords per measure with
  full-melody context. New **♪ Harmonize Last** button in the GUI.
- **Offline renderer** (`voice_to_piano/render.py`): renders any MIDI / music21
  Score to a WAV file via FluidSynth without going through the live audio loop.
- **Diatonic chord modes** (`Diatonic triad`, `Diatonic 7th`) — key-aware chord
  selection that picks I/ii/iii/IV/V/vi/vii° based on the sung note.
- **24-key selector** (12 major + 12 minor) feeding the diatonic logic.
- **Genre presets**: Pop / Jazz / Classical / Beatles / Custom — bundle
  Instrument + Chord + Bass + V7 into a single switch.
- **Bass octaves** picker and **V→V7** toggle for cadence flavour.
- **18 General MIDI instruments** including Violin, Cello, String Ensemble,
  Flute, Trumpet, Rhodes, etc.
- **MusicXML export** alongside WAV + MIDI on every recording, with detected
  key signature and 16th-note / triplet quantization.
- **Chord recipe table** with 13 shapes: Octave variants, Power, Triads, 7ths,
  Sus4, Bass + triad combinations.
- **Test suite** (`tests/`): pitch detection, diatonic harmony, genres.
- **Dev tooling**: ruff lint config, pytest, GitHub Actions CI matrix
  (Python 3.11 / 3.12 / 3.13 on Ubuntu).
- OSS docs: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, issue +
  pull-request templates.

### Changed
- **Engine refactor**: FluidSynth is now driven manually via `OutputStream`
  callback (was `fs.start(driver="coreaudio")`), which lets the same sample
  stream feed both the speaker and the WAV recorder.
- **Polyphonic note tracking**: replaced single `_current_note` with a set of
  active notes so chord mode only re-triggers notes that actually change.
- Default chord mode is now `Diatonic triad` (was `Off (mono)`).

### Fixed
- pyfluidsynth library lookup on macOS Apple Silicon (sets `HOMEBREW_PREFIX`
  before import so `find_library('fluidsynth')` succeeds).

## [0.1.0] - 2026-05-20

### Added
- Initial release: real-time voice-to-piano with PySide6 GUI.
- FFT autocorrelation pitch detection feeding FluidSynth piano output.
- 88-key piano widget with highlighted active key, VU meter, threshold /
  confidence sliders, microphone selector.
- WAV + MIDI recording.
- Download script for GeneralUser GS SoundFont.

[Unreleased]: https://github.com/gclinian/voice_music_transformer/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/gclinian/voice_music_transformer/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/gclinian/voice_music_transformer/releases/tag/v0.1.0
