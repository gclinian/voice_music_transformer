"""PySide6 GUI: piano keyboard + VU meter + sliders + note label."""

from __future__ import annotations

from pathlib import Path

import sounddevice as sd
from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
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

from .audio_engine import AudioEngine, PIANO_MAX_MIDI, PIANO_MIN_MIDI
from .pitch import midi_to_note_name

# MIDI 21..108 is the 88-key range. Whites are non-{1,3,6,8,10} mod 12.
_BLACK_KEY_PCS = {1, 3, 6, 8, 10}


def _is_black(midi: int) -> bool:
    return (midi % 12) in _BLACK_KEY_PCS


class PianoKeyboardWidget(QWidget):
    """88-key piano. Call set_active_note(midi) to highlight."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active: int | None = None
        self.setMinimumHeight(110)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())

    def sizeHint(self) -> QSize:
        return QSize(880, 120)

    def set_active_note(self, midi: int | None) -> None:
        if midi == self._active:
            return
        self._active = midi
        self.update()

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

        # Draw white keys
        for i, midi in enumerate(whites):
            rect = QRectF(i * wkey_w, 0, wkey_w, wkey_h)
            if midi == self._active:
                grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
                grad.setColorAt(0.0, QColor(120, 200, 255))
                grad.setColorAt(1.0, QColor(60, 140, 220))
                painter.fillRect(rect, QBrush(grad))
            else:
                painter.fillRect(rect, QColor(252, 252, 250))
            painter.setPen(QPen(QColor(90, 90, 90), 0.8))
            painter.drawRect(rect)

            if midi % 12 == 0:  # label C notes
                painter.setPen(QColor(120, 120, 120))
                painter.setFont(QFont("Helvetica", 8))
                painter.drawText(
                    rect.adjusted(2, 0, -2, -4),
                    int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft),
                    midi_to_note_name(midi),
                )

        # Draw black keys on top.
        white_idx = {m: i for i, m in enumerate(whites)}
        for midi in range(PIANO_MIN_MIDI, PIANO_MAX_MIDI + 1):
            if not _is_black(midi):
                continue
            # Position: between the white key just below and this black key.
            left_white = midi - 1
            if left_white not in white_idx:
                continue
            x = (white_idx[left_white] + 1) * wkey_w - bkey_w / 2
            rect = QRectF(x, 0, bkey_w, bkey_h)
            if midi == self._active:
                grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
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


class MainWindow(QMainWindow):
    def __init__(self, soundfont_path: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Voice → Piano")
        self.resize(960, 360)

        self._soundfont_path = soundfont_path or ""
        self._engine: AudioEngine | None = None

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

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.record_btn)
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
        self.keyboard.set_active_note(None)
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

    def _on_recording_saved(self, wav_path: str, midi_path: str) -> None:
        wav_name = Path(wav_path).name
        midi_name = Path(midi_path).name
        self.status_label.setText(f"Saved: {wav_name} + {midi_name}")

    def _on_note(self, midi: int, freq: float, velocity: int) -> None:
        self.note_label.setText(midi_to_note_name(midi))
        self.freq_label.setText(f"{freq:.1f} Hz · MIDI {midi} · vel {velocity}")
        self.keyboard.set_active_note(midi)

    def _on_release(self) -> None:
        self.keyboard.set_active_note(None)

    def _on_error(self, msg: str) -> None:
        QMessageBox.critical(self, "Audio error", msg)
        self._stop_engine()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._engine is not None:
            self._engine.stop()
        event.accept()
