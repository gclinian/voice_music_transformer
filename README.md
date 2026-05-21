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
- **Genre**：高階風格 preset，一鍵把 Instrument / Chord / Bass / V7 全部設好
  - `Pop` — Bright Piano + diatonic triads
  - `Jazz` — Rhodes + diatonic 7ths + 根音 bass + V7
  - `Classical` — Grand Piano + diatonic triads + 八度 bass
  - `Beatles` — Grand Piano + diatonic triads + V7 終止式
  - `Custom` — 完全手動
- **Key**：24 個調 (12 大 + 12 小)。Diatonic 模式會用這個決定每個音應該配哪種和弦
- **Instrument**：18 種 General MIDI 樂器 (Piano、Violin、Cello、Flute、Trumpet…) 即時切換
- **Chord**：13 種和弦模式
  - `Diatonic triad` (預設) / `Diatonic 7th` — 看 Key 決定 (例如 C 大調裡 D 自動配 Dm)
  - `Major / Minor triad`、`Sus4`、`Power`、`Major 7`、`Minor 7`、`Octave`、`Bass + triad`、`Off (mono)`
- **Bass octaves**：根音下移幾個八度 (0 / 1 / 2)
- **V → V7**：勾起來讓 V 級和弦升級為屬七 (Beatles 終止式)
- **Start / Stop**：開關引擎
- **● Record**：按下開始錄，再按一下停。同時存三個檔到 `recordings/`：
  - `piano_2026-05-21_00-07-12.wav` — 樂器音訊 (44.1 kHz / stereo / int16)，包含和弦
  - `piano_2026-05-21_00-07-12.mid` — MIDI，可以丟進 GarageBand/Logic 換音色或編輯
  - `piano_2026-05-21_00-07-12.musicxml` — 樂譜檔，量化過拍子與調號，免費的 MuseScore 開啟即看五線譜
- **♪ Harmonize Last**：兩段式工作流。先把 Chord 切到 `Off (mono)` 錄純旋律 → 點這顆，引擎會：
  1. 用 Krumhansl-Schmuckler 演算法從整段旋律偵測 key
  2. 把旋律切成小節 (一小節一個和弦)
  3. 每小節挑最符合該段音的 diatonic 和弦，並用 V→I / ii→V 等常見進行的 bonus 做前後文修正
  4. 末小節若旋律落在主音，強制配 I 收尾
  5. 多存三個檔：`piano_*_harmonized.{wav,mid,musicxml}`
  
  測試結果：Mary had a little lamb 自動配 `I → I → V → I`；Twinkle Twinkle 配 `I → V → ii → V → ii → I → V → I`

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
