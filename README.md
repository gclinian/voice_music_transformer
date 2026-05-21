# voice-to-piano

唱歌、哼歌或吹口哨 → 即時聽到鋼琴音。PySide6 GUI。

Pipeline: mic → autocorrelation pitch detection → MIDI note → FluidSynth piano → speaker.

## Setup (macOS)

```sh
# 1. FluidSynth (audio synthesis backend)
brew install fluid-synth

# 2. Python deps (uv handles the .venv with Python 3.11)
uv sync

# 3. Download a piano SoundFont (~31 MB GeneralUser GS)
./scripts/download_soundfont.sh
```

## Run

```sh
uv run python main.py
```

GUI 操作：
1. 確認 `Settings → SoundFont` 已經指到 `.sf2` 檔
2. 選擇麥克風 (預設用系統預設輸入)
3. 點 **Start**
4. 對著麥克風唱／哼／吹口哨

## GUI components

- **大字音名顯示**：當下偵測到的音 (例如 `A4`)
- **頻率/MIDI/velocity**：即時 debug 資訊
- **88 鍵鋼琴**：彈到的鍵會高亮
- **VU meter**：麥克風音量，白色細線是 threshold
- **滑桿**：
  - `Threshold` — 環境吵就調高，避免靜音被誤判
  - `Confidence` — 口哨/唱歌不穩可以調高
- **Instrument**：18 種 General MIDI 樂器 (Piano、Violin、Cello、Flute、Trumpet…) 即時切換
- **Chord**：11 種和弦模式 — Off (單音)、Major / Minor triad、Sus4、Power、Major 7、Minor 7、Bass + triad 等。預設 Major triad
- **Start / Stop**：開關引擎
- **● Record**：按下開始錄，再按一下停。同時存兩個檔到 `recordings/`：
  - `piano_2026-05-21_00-07-12.wav` — 樂器音訊 (44.1 kHz / stereo / int16)，包含和弦
  - `piano_2026-05-21_00-07-12.mid` — MIDI (note on/off + 時間)，可以丟進 GarageBand/Logic 換音色或編輯

## Project layout

```
main.py                       # entrypoint
voice_to_piano/
  pitch.py                    # FFT autocorrelation pitch detection
  audio_engine.py             # AudioEngine: mic → pitch → FluidSynth, Qt signals
  ui.py                       # PySide6 MainWindow, piano keyboard, VU meter
scripts/
  download_soundfont.sh
soundfonts/
  GeneralUser.sf2             # bank 0 preset 0 = Grand Piano
```

## Limitations

- **Monophonic**：一次只發一個音
- **Latency**：block 2048 samples @ 44.1 kHz ≈ 46 ms 偵測 + FluidSynth 緩衝 ~ 整體 100 ms 左右
- **Voice range**：70 Hz – 1100 Hz

## Roadmap

- [ ] Polyphonic mode via Spotify `basic-pitch`
- [ ] 錄音模式 (sing → export MIDI/wav)
- [ ] 視覺化最近彈過的音 (piano roll)
