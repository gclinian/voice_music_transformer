# Contributing

Thanks for your interest! This is a small project — bug reports, ideas, and PRs of any size are welcome.

## Development setup

1. **System dependencies** (macOS shown; the [README](README.md) has Linux/Windows hints):
   ```sh
   brew install fluid-synth
   ```
2. **Clone and sync**:
   ```sh
   git clone https://github.com/gclinian/voice_music_transformer.git
   cd voice_music_transformer
   uv sync --group dev
   ./scripts/download_soundfont.sh
   ```
3. **Run the app**:
   ```sh
   uv run python main.py
   ```

## Before you push

```sh
uv run ruff check .       # lint
uv run ruff format .      # format (optional but appreciated)
uv run pytest             # tests
```

If you change UI or audio behaviour, please do a manual run with the app and confirm the feature you touched still works — automated tests don't cover the GUI loop or the live mic path.

## Project layout

```
main.py                       Entry point: parse CLI args, launch QApplication.
voice_to_piano/
  pitch.py                    FFT autocorrelation pitch detection.
  harmony.py                  Keys, scale degrees, diatonic chord lookup.
  harmonizer.py               Post-hoc chord generation (whole-melody context).
  instruments.py              GM instrument list + chord recipe table.
  genres.py                   Genre presets (Pop / Jazz / Classical / Beatles).
  audio_engine.py             Mic in → pitch → FluidSynth → speaker; recording.
  render.py                   Offline MIDI→WAV using FluidSynth.
  ui.py                       PySide6 MainWindow + custom keyboard / VU widgets.
tests/
  test_pitch.py
  test_harmony.py
  test_genres.py
scripts/
  download_soundfont.sh       Pull GeneralUser GS (~31 MB).
```

## Style

- **Ruff** is the source of truth (`pyproject.toml` → `[tool.ruff]`). 100-char lines.
- **No spurious comments.** Name things well and let the code speak.
- **No backwards-compat shims** unless they're load-bearing — this is a small app, not a library API.
- **One PR ≈ one idea.** Smaller is faster to review.

## Submitting a PR

1. Fork, branch from `main`.
2. Make your change.
3. `ruff check` + `pytest` green.
4. Open the PR with the template filled in.

We'll usually respond within a few days. If you don't hear back, ping the PR.

## Adding things you might want to add

- **New instrument**: append a `(name, GM program number)` row to `voice_to_piano/instruments.py::INSTRUMENTS`.
- **New chord shape**: add a `(name, interval tuple)` row to `CHORD_RECIPES` in the same file.
- **New genre**: append a `Genre(...)` to `voice_to_piano/genres.py::GENRES`. The preset just sets dependent dropdowns when picked.
- **Better harmonization**: hack `voice_to_piano/harmonizer.py::harmonize_melody`. The scoring function is the central knob — tests in `tests/` make it easy to A/B.

## License

By contributing, you agree your changes will be released under this project's [MIT License](LICENSE).
