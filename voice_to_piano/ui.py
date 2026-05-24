"""PySide6 GUI: piano keyboard + VU meter + sliders + note label."""

from __future__ import annotations

from pathlib import Path

import sounddevice as sd
from PySide6.QtCore import QObject, QRectF, QSize, Qt, QThread, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .audio_engine import PIANO_MAX_MIDI, PIANO_MIN_MIDI, AudioEngine
from .genres import GENRES, get_genre
from .harmonizer import harmonize_melody
from .harmony import KEYS
from .instruments import (
    CHORD_RECIPES,
    DEFAULT_CHORD,
    DEFAULT_INSTRUMENT_PROGRAM,
    DEFAULT_KEY,
    INSTRUMENTS,
)
from .patterns import DEFAULT_BPM, DEFAULT_PATTERN, PATTERNS
from .pitch import midi_to_note_name
from .render import render_score_to_wav

# MIDI 21..108 is the 88-key range. Whites are non-{1,3,6,8,10} mod 12.
_BLACK_KEY_PCS = {1, 3, 6, 8, 10}


def _is_black(midi: int) -> bool:
    return (midi % 12) in _BLACK_KEY_PCS


class PianoKeyboardWidget(QWidget):
    """88-key piano. Set highlighted notes via set_active_notes(set/list)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active: set[int] = set()
        self._root: int | None = None
        self.setMinimumHeight(110)

    def sizeHint(self) -> QSize:
        return QSize(880, 120)

    def set_active_notes(self, notes, root: int | None = None) -> None:
        new = set(notes) if notes else set()
        if new == self._active and root == self._root:
            return
        self._active = new
        self._root = root
        self.update()

    def clear(self) -> None:
        self.set_active_notes(set(), None)

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        whites = [m for m in range(PIANO_MIN_MIDI, PIANO_MAX_MIDI + 1) if not _is_black(m)]
        n_whites = len(whites)
        width = self.width()
        height = self.height()
        wkey_w = width / n_whites
        wkey_h = height
        bkey_w = wkey_w * 0.58
        bkey_h = wkey_h * 0.62

        # White keys
        for i, midi in enumerate(whites):
            rect = QRectF(i * wkey_w, 0, wkey_w, wkey_h)
            if midi in self._active:
                grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
                if midi == self._root:
                    grad.setColorAt(0.0, QColor(255, 170, 80))
                    grad.setColorAt(1.0, QColor(220, 110, 30))
                else:
                    grad.setColorAt(0.0, QColor(120, 200, 255))
                    grad.setColorAt(1.0, QColor(60, 140, 220))
                painter.fillRect(rect, QBrush(grad))
            else:
                painter.fillRect(rect, QColor(252, 252, 250))
            painter.setPen(QPen(QColor(90, 90, 90), 0.8))
            painter.drawRect(rect)

            if midi % 12 == 0:
                painter.setPen(QColor(120, 120, 120))
                painter.setFont(QFont("Helvetica", 8))
                painter.drawText(
                    rect.adjusted(2, 0, -2, -4),
                    int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft),
                    midi_to_note_name(midi),
                )

        # Black keys
        white_idx = {m: i for i, m in enumerate(whites)}
        for midi in range(PIANO_MIN_MIDI, PIANO_MAX_MIDI + 1):
            if not _is_black(midi):
                continue
            left_white = midi - 1
            if left_white not in white_idx:
                continue
            x = (white_idx[left_white] + 1) * wkey_w - bkey_w / 2
            rect = QRectF(x, 0, bkey_w, bkey_h)
            if midi in self._active:
                grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
                if midi == self._root:
                    grad.setColorAt(0.0, QColor(220, 120, 40))
                    grad.setColorAt(1.0, QColor(140, 60, 10))
                else:
                    grad.setColorAt(0.0, QColor(40, 110, 200))
                    grad.setColorAt(1.0, QColor(20, 60, 140))
                painter.fillRect(rect, QBrush(grad))
            else:
                painter.fillRect(rect, QColor(20, 20, 20))
            painter.setPen(QPen(QColor(0, 0, 0), 0.5))
            painter.drawRect(rect)

        painter.end()


class VUMeter(QWidget):
    """Horizontal level meter with threshold tick."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._level = 0.0
        self._threshold = 0.01
        self.setMinimumHeight(22)
        self.setMinimumWidth(200)

    def set_level(self, value: float) -> None:
        # log scale-ish for visual range; clamp to [0, 1].
        v = min(1.0, max(0.0, value * 3.0))
        if abs(v - self._level) < 1e-3:
            return
        self._level = v
        self.update()

    def set_threshold(self, value: float) -> None:
        self._threshold = min(1.0, max(0.0, value * 3.0))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        painter.fillRect(0, 0, w, h, QColor(30, 30, 30))

        bar_w = int(w * self._level)
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QColor(80, 200, 120))
        grad.setColorAt(0.65, QColor(240, 220, 80))
        grad.setColorAt(1.0, QColor(230, 70, 70))
        painter.fillRect(0, 0, bar_w, h, QBrush(grad))

        # Threshold tick
        tx = int(w * self._threshold)
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1.5))
        painter.drawLine(tx, 0, tx, h)

        painter.setPen(QPen(QColor(80, 80, 80), 1))
        painter.drawRect(0, 0, w - 1, h - 1)
        painter.end()


class HarmonizeWorker(QObject):
    """Run harmonize_melody + render_score_to_wav off the UI thread."""

    finished = Signal(str, str, str, str, str)  # midi, xml, wav, key_label, progression
    failed = Signal(str)

    def __init__(self, midi_path: str, soundfont: str, window_ql: float) -> None:
        super().__init__()
        self._midi_path = midi_path
        self._soundfont = soundfont
        self._window_ql = window_ql

    def run(self) -> None:
        try:
            base = Path(self._midi_path).with_suffix("")
            xml_out = str(base) + "_harmonized.musicxml"
            mid_out = str(base) + "_harmonized.mid"
            wav_out = str(base) + "_harmonized.wav"

            result = harmonize_melody(self._midi_path, window_ql=self._window_ql)
            result.score.write("musicxml", fp=xml_out)
            result.score.write("midi", fp=mid_out)
            render_score_to_wav(result.score, self._soundfont, wav_out, program=0)

            key_label = f"{result.detected_key.tonic.name} {result.detected_key.mode}"
            progression = " → ".join(result.progression)
            self.finished.emit(mid_out, xml_out, wav_out, key_label, progression)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, soundfont_path: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Voice → Piano")
        self.resize(960, 380)

        self._soundfont_path = soundfont_path or ""
        self._engine: AudioEngine | None = None
        self._last_midi_path: str | None = None
        self._harmonize_thread: QThread | None = None
        self._harmonize_worker: HarmonizeWorker | None = None

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Top row: note display
        self.note_label = QLabel("—")
        f = QFont("Helvetica", 36, QFont.Weight.Bold)
        self.note_label.setFont(f)
        self.note_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.freq_label = QLabel("Press Start to listen")
        self.freq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.freq_label.setStyleSheet("color: #888;")

        root.addWidget(self.note_label)
        root.addWidget(self.freq_label)

        # Keyboard
        self.keyboard = PianoKeyboardWidget()
        root.addWidget(self.keyboard)

        # VU meter row
        vu_row = QHBoxLayout()
        vu_row.addWidget(QLabel("Mic"))
        self.vu = VUMeter()
        vu_row.addWidget(self.vu, stretch=1)
        root.addLayout(vu_row)

        # Settings panel
        settings = QGroupBox("Settings")
        sl = QVBoxLayout(settings)

        # Genre row (high-level preset)
        genre_row = QHBoxLayout()
        genre_row.addWidget(QLabel("Genre"))
        self.genre_combo = QComboBox()
        for g in GENRES:
            self.genre_combo.addItem(g.name, g.name)
            self.genre_combo.setItemData(
                self.genre_combo.count() - 1, g.blurb, Qt.ItemDataRole.ToolTipRole
            )
        self.genre_combo.setCurrentText("Pop")
        self.genre_combo.currentTextChanged.connect(self._on_genre_changed)
        genre_row.addWidget(self.genre_combo, stretch=1)

        genre_row.addSpacing(12)
        genre_row.addWidget(QLabel("Key"))
        self.key_combo = QComboBox()
        for name, _, _ in KEYS:
            self.key_combo.addItem(name)
        self.key_combo.setCurrentText(DEFAULT_KEY)
        self.key_combo.currentTextChanged.connect(self._on_key_changed)
        genre_row.addWidget(self.key_combo, stretch=1)
        sl.addLayout(genre_row)

        # Instrument + Chord row
        inst_row = QHBoxLayout()
        inst_row.addWidget(QLabel("Instrument"))
        self.instrument_combo = QComboBox()
        for name, program in INSTRUMENTS:
            self.instrument_combo.addItem(name, program)
            if program == DEFAULT_INSTRUMENT_PROGRAM:
                self.instrument_combo.setCurrentIndex(self.instrument_combo.count() - 1)
        self.instrument_combo.currentIndexChanged.connect(self._on_instrument_changed)
        inst_row.addWidget(self.instrument_combo, stretch=1)

        inst_row.addSpacing(12)
        inst_row.addWidget(QLabel("Chord"))
        self.chord_combo = QComboBox()
        for name in CHORD_RECIPES:
            self.chord_combo.addItem(name)
            if name == DEFAULT_CHORD:
                self.chord_combo.setCurrentIndex(self.chord_combo.count() - 1)
        self.chord_combo.currentTextChanged.connect(self._on_chord_changed)
        inst_row.addWidget(self.chord_combo, stretch=1)
        sl.addLayout(inst_row)

        # Pattern + BPM row
        pat_row = QHBoxLayout()
        pat_row.addWidget(QLabel("Pattern"))
        self.pattern_combo = QComboBox()
        for name, pat in PATTERNS.items():
            self.pattern_combo.addItem(name)
            self.pattern_combo.setItemData(
                self.pattern_combo.count() - 1, pat.blurb, Qt.ItemDataRole.ToolTipRole
            )
            if name == DEFAULT_PATTERN:
                self.pattern_combo.setCurrentIndex(self.pattern_combo.count() - 1)
        self.pattern_combo.currentTextChanged.connect(self._on_pattern_changed)
        pat_row.addWidget(self.pattern_combo, stretch=1)

        pat_row.addSpacing(12)
        pat_row.addWidget(QLabel("BPM"))
        self.bpm_slider = QSlider(Qt.Orientation.Horizontal)
        self.bpm_slider.setRange(40, 200)
        self.bpm_slider.setValue(DEFAULT_BPM)
        self.bpm_val = QLabel(str(DEFAULT_BPM))
        self.bpm_val.setMinimumWidth(36)
        self.bpm_val.setStyleSheet("color: #555;")

        def on_bpm(v: int) -> None:
            self.bpm_val.setText(str(v))
            if self._engine is not None:
                self._engine.set_bpm(v)

        self.bpm_slider.valueChanged.connect(on_bpm)
        pat_row.addWidget(self.bpm_slider, stretch=1)
        pat_row.addWidget(self.bpm_val)
        sl.addLayout(pat_row)

        # Bass octaves + V7 toggle
        bass_row = QHBoxLayout()
        bass_row.addWidget(QLabel("Bass octaves"))
        self.bass_combo = QComboBox()
        for label, octaves in [("Off", 0), ("1 octave down", 1), ("2 octaves down", 2)]:
            self.bass_combo.addItem(label, octaves)
        self.bass_combo.currentIndexChanged.connect(self._on_bass_changed)
        bass_row.addWidget(self.bass_combo, stretch=1)
        bass_row.addSpacing(12)
        self.dom7_check = QCheckBox("V → V7 (dominant cadence)")
        self.dom7_check.toggled.connect(self._on_dom7_changed)
        bass_row.addWidget(self.dom7_check, stretch=1)
        sl.addLayout(bass_row)

        # Input device
        dev_row = QHBoxLayout()
        dev_row.addWidget(QLabel("Input"))
        self.device_combo = QComboBox()
        self._populate_devices()
        dev_row.addWidget(self.device_combo, stretch=1)
        sl.addLayout(dev_row)

        # SoundFont
        sf_row = QHBoxLayout()
        sf_row.addWidget(QLabel("SoundFont"))
        self.sf_label = QLabel(self._soundfont_path or "(not set)")
        self.sf_label.setStyleSheet("color: #555;")
        sf_row.addWidget(self.sf_label, stretch=1)
        sf_btn = QPushButton("Browse…")
        sf_btn.clicked.connect(self._pick_soundfont)
        sf_row.addWidget(sf_btn)
        sl.addLayout(sf_row)

        # Threshold slider
        self.threshold_slider, threshold_row, self.threshold_val = self._make_slider(
            "Threshold", 0, 100, 10, "{:.2f}", scale=0.01
        )
        sl.addLayout(threshold_row)

        # Confidence slider
        self.confidence_slider, confidence_row, self.confidence_val = self._make_slider(
            "Confidence", 5, 80, 30, "{:.2f}", scale=0.01
        )
        sl.addLayout(confidence_row)

        root.addWidget(settings)

        # Start/stop + Record buttons
        self.start_btn = QPushButton("Start")
        self.start_btn.setStyleSheet(
            "QPushButton { padding: 10px 24px; font-size: 14px; font-weight: 600; }"
        )
        self.start_btn.clicked.connect(self._toggle_engine)

        self.record_btn = QPushButton("● Record")
        self.record_btn.setEnabled(False)
        self.record_btn.setStyleSheet(self._record_btn_style(active=False))
        self.record_btn.clicked.connect(self._toggle_recording)

        self.harmonize_btn = QPushButton("♪ Harmonize Last")
        self.harmonize_btn.setEnabled(False)
        self.harmonize_btn.setToolTip(
            "Read the last recording's MIDI, detect key, add chords per measure,\n"
            "and save *_harmonized.{wav,mid,musicxml}. Use this after recording\n"
            "with Chord = Off (mono) to keep the melody clean and add chords later."
        )
        self.harmonize_btn.setStyleSheet(
            "QPushButton { padding: 10px 20px; font-size: 14px; font-weight: 600;"
            " color: #2c7; }"
            "QPushButton:disabled { color: #aaa; }"
        )
        self.harmonize_btn.clicked.connect(self._run_harmonize)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.record_btn)
        btn_row.addWidget(self.harmonize_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # Status line for recording / saved files
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #666; font-size: 11px;")
        root.addWidget(self.status_label)

        self.setCentralWidget(central)

        # Initial threshold tick in VU
        self.vu.set_threshold(self.threshold_slider.value() * 0.01)

    # --- UI helpers -------------------------------------------------------

    def _make_slider(
        self,
        label: str,
        min_val: int,
        max_val: int,
        init: int,
        fmt: str,
        scale: float,
    ) -> tuple[QSlider, QHBoxLayout, QLabel]:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setMinimumWidth(80)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(init)
        val_label = QLabel(fmt.format(init * scale))
        val_label.setMinimumWidth(48)
        val_label.setStyleSheet("color: #555;")

        def on_change(v: int) -> None:
            val_label.setText(fmt.format(v * scale))
            if self._engine is None:
                return
            if label == "Threshold":
                self._engine.set_threshold(v * scale)
                self.vu.set_threshold(v * scale)
            elif label == "Confidence":
                self._engine.set_confidence(v * scale)

        slider.valueChanged.connect(on_change)
        row.addWidget(lbl)
        row.addWidget(slider, stretch=1)
        row.addWidget(val_label)
        return slider, row, val_label

    def _populate_devices(self) -> None:
        self.device_combo.clear()
        self.device_combo.addItem("System default", None)
        try:
            devices = sd.query_devices()
            default_in = sd.default.device[0]
        except Exception:
            return
        for i, d in enumerate(devices):
            if d.get("max_input_channels", 0) <= 0:
                continue
            label = f"{i}: {d['name']}"
            self.device_combo.addItem(label, i)
            if i == default_in:
                self.device_combo.setCurrentIndex(self.device_combo.count() - 1)

    def _pick_soundfont(self) -> None:
        start_dir = str(Path(self._soundfont_path).parent) if self._soundfont_path else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose SoundFont", start_dir, "SoundFont (*.sf2 *.sf3)"
        )
        if not path:
            return
        self._soundfont_path = path
        self.sf_label.setText(path)

    # --- engine wiring ----------------------------------------------------

    @staticmethod
    def _record_btn_style(active: bool) -> str:
        if active:
            return (
                "QPushButton { padding: 10px 20px; font-size: 14px; font-weight: 600;"
                " background-color: #d33; color: white; border-radius: 4px; }"
            )
        return (
            "QPushButton { padding: 10px 20px; font-size: 14px; font-weight: 600;"
            " color: #d33; }"
            "QPushButton:disabled { color: #aaa; }"
        )

    def _toggle_engine(self) -> None:
        if self._engine is not None and self._engine.is_running():
            self._stop_engine()
        else:
            self._start_engine()

    def _start_engine(self) -> None:
        if not self._soundfont_path or not Path(self._soundfont_path).exists():
            QMessageBox.warning(
                self,
                "No SoundFont",
                "Pick a .sf2 file first (Settings → SoundFont → Browse…).",
            )
            return

        device = self.device_combo.currentData()
        self._engine = AudioEngine(
            soundfont_path=self._soundfont_path,
            input_device=device,
            rms_threshold=self.threshold_slider.value() * 0.01,
            confidence=self.confidence_slider.value() * 0.01,
            instrument_program=self.instrument_combo.currentData(),
            chord_mode=self.chord_combo.currentText(),
            key_label=self.key_combo.currentText(),
            bass_octaves=self.bass_combo.currentData(),
            dom7_on_v=self.dom7_check.isChecked(),
            pattern=self.pattern_combo.currentText(),
            bpm=self.bpm_slider.value(),
        )
        self._engine.levelChanged.connect(self.vu.set_level)
        self._engine.notePlayed.connect(self._on_note)
        self._engine.noteReleased.connect(self._on_release)
        self._engine.errorOccurred.connect(self._on_error)
        self._engine.recordingStateChanged.connect(self._on_recording_changed)
        self._engine.recordingSaved.connect(self._on_recording_saved)
        self._engine.start()

        self.start_btn.setText("Stop")
        self.record_btn.setEnabled(True)
        self.freq_label.setText("Listening…")
        self.status_label.setText("")

    def _stop_engine(self) -> None:
        if self._engine is not None:
            self._engine.stop()
            self._engine = None
        self.start_btn.setText("Start")
        self.record_btn.setEnabled(False)
        self.record_btn.setText("● Record")
        self.record_btn.setStyleSheet(self._record_btn_style(active=False))
        self.freq_label.setText("Stopped")
        self.note_label.setText("—")
        self.keyboard.clear()
        self.vu.set_level(0.0)

    def _toggle_recording(self) -> None:
        if self._engine is None:
            return
        if self._engine.is_recording():
            self._engine.stop_recording()
        else:
            self._engine.start_recording()

    def _on_recording_changed(self, active: bool) -> None:
        if active:
            self.record_btn.setText("■ Stop Recording")
            self.record_btn.setStyleSheet(self._record_btn_style(active=True))
            self.status_label.setText("Recording…")
        else:
            self.record_btn.setText("● Record")
            self.record_btn.setStyleSheet(self._record_btn_style(active=False))

    def _on_recording_saved(
        self, wav_path: str, midi_path: str, musicxml_path: str
    ) -> None:
        parts = [Path(wav_path).name, Path(midi_path).name]
        if musicxml_path:
            parts.append(Path(musicxml_path).name)
        self.status_label.setText("Saved: " + " + ".join(parts))
        self._last_midi_path = midi_path
        self.harmonize_btn.setEnabled(bool(self._soundfont_path))

    def _run_harmonize(self) -> None:
        if (
            self._last_midi_path is None
            or not Path(self._last_midi_path).exists()
            or not self._soundfont_path
        ):
            QMessageBox.warning(self, "Harmonize", "No recording to harmonize yet.")
            return
        if self._harmonize_thread is not None:
            return  # already running

        self.harmonize_btn.setEnabled(False)
        self.status_label.setText("Harmonizing…")

        self._harmonize_thread = QThread()
        self._harmonize_worker = HarmonizeWorker(
            midi_path=self._last_midi_path,
            soundfont=self._soundfont_path,
            window_ql=4.0,  # one chord per measure
        )
        self._harmonize_worker.moveToThread(self._harmonize_thread)
        self._harmonize_thread.started.connect(self._harmonize_worker.run)
        self._harmonize_worker.finished.connect(self._on_harmonize_done)
        self._harmonize_worker.failed.connect(self._on_harmonize_failed)
        self._harmonize_worker.finished.connect(self._cleanup_harmonize_thread)
        self._harmonize_worker.failed.connect(self._cleanup_harmonize_thread)
        self._harmonize_thread.start()

    def _on_harmonize_done(
        self,
        mid_path: str,
        xml_path: str,
        wav_path: str,
        key_label: str,
        progression: str,
    ) -> None:
        msg = (
            f"Harmonized in {key_label} — {progression}\n"
            f"Saved: {Path(wav_path).name} + {Path(mid_path).name} + {Path(xml_path).name}"
        )
        self.status_label.setText(msg)

    def _on_harmonize_failed(self, msg: str) -> None:
        self.status_label.setText("")
        QMessageBox.warning(self, "Harmonize failed", msg)

    def _cleanup_harmonize_thread(self, *_args) -> None:
        if self._harmonize_thread is not None:
            self._harmonize_thread.quit()
            self._harmonize_thread.wait(2000)
        self._harmonize_thread = None
        self._harmonize_worker = None
        self.harmonize_btn.setEnabled(self._last_midi_path is not None)

    def _on_note(self, midi: int, freq: float, velocity: int, chord) -> None:
        self.note_label.setText(midi_to_note_name(midi))
        chord_names = " · ".join(midi_to_note_name(n) for n in chord)
        if len(chord) > 1:
            self.freq_label.setText(
                f"{freq:.1f} Hz · root MIDI {midi} · vel {velocity}  →  {chord_names}"
            )
        else:
            self.freq_label.setText(f"{freq:.1f} Hz · MIDI {midi} · vel {velocity}")
        self.keyboard.set_active_notes(chord, root=midi)

    def _on_release(self) -> None:
        self.keyboard.clear()

    def _on_instrument_changed(self, _index: int) -> None:
        if self._engine is not None:
            self._engine.set_instrument(self.instrument_combo.currentData())

    def _on_chord_changed(self, mode: str) -> None:
        if self._engine is not None:
            self._engine.set_chord_mode(mode)

    def _on_key_changed(self, label: str) -> None:
        if self._engine is not None:
            self._engine.set_key(label)

    def _on_bass_changed(self, _index: int) -> None:
        if self._engine is not None:
            self._engine.set_bass_octaves(self.bass_combo.currentData())

    def _on_dom7_changed(self, checked: bool) -> None:
        if self._engine is not None:
            self._engine.set_dom7_on_v(checked)

    def _on_pattern_changed(self, name: str) -> None:
        if self._engine is not None:
            self._engine.set_pattern(name)

    def _on_genre_changed(self, name: str) -> None:
        g = get_genre(name)
        if g is None or name == "Custom":
            return
        # Set all dependent widgets; their signals propagate to the engine.
        if g.chord_mode in CHORD_RECIPES:
            self.chord_combo.setCurrentText(g.chord_mode)
        for i in range(self.instrument_combo.count()):
            if self.instrument_combo.itemData(i) == g.instrument_program:
                self.instrument_combo.setCurrentIndex(i)
                break
        for i in range(self.bass_combo.count()):
            if self.bass_combo.itemData(i) == g.bass_octaves:
                self.bass_combo.setCurrentIndex(i)
                break
        self.dom7_check.setChecked(g.dom7_on_V)
        if g.pattern and g.pattern in PATTERNS:
            self.pattern_combo.setCurrentText(g.pattern)
        if g.bpm:
            self.bpm_slider.setValue(g.bpm)

    def _on_error(self, msg: str) -> None:
        QMessageBox.critical(self, "Audio error", msg)
        self._stop_engine()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._engine is not None:
            self._engine.stop()
        event.accept()
