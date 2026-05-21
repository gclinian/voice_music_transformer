"""Audio engine: mic capture -> pitch detection -> FluidSynth -> speaker.

FluidSynth is rendered manually (not via fs.start(driver=...)) so we can also
capture the piano output to a WAV file when recording is on. MIDI events are
collected in parallel for .mid export.

Threads:
- sounddevice input callback  -> _audio_q (mic frames in)
- sounddevice output callback -> renders piano from FluidSynth (real-time)
- worker thread               -> drains _audio_q, detects pitch, triggers notes
"""

from __future__ import annotations

import datetime as dt
import os
import queue
import threading
import time
import wave
from pathlib import Path

# pyfluidsynth's find_library fails on macOS Apple Silicon — point it at Homebrew.
os.environ.setdefault("HOMEBREW_PREFIX", "/opt/homebrew")

import fluidsynth  # noqa: E402
import mido  # noqa: E402
import numpy as np  # noqa: E402
import sounddevice as sd  # noqa: E402
from PySide6.QtCore import QObject, Signal  # noqa: E402

from .harmony import diatonic_chord_notes, key_label_to_tonic  # noqa: E402
from .instruments import (  # noqa: E402
    CHORD_RECIPES,
    DEFAULT_CHORD,
    DEFAULT_INSTRUMENT_PROGRAM,
    DEFAULT_KEY,
    DIATONIC_MODES,
)
from .pitch import detect_pitch_autocorr, freq_to_midi  # noqa: E402

SAMPLE_RATE = 44100
BLOCK_SIZE = 2048
OUTPUT_BLOCK = 512  # smaller blocks for output -> lower latency
PIANO_MIN_MIDI = 21
PIANO_MAX_MIDI = 108


class AudioEngine(QObject):
    """Mic in -> pitch detection -> FluidSynth -> output stream.

    Qt signals are emitted from background threads; Qt queues them to the UI.
    """

    levelChanged = Signal(float)
    # detected root note: midi, freq_hz, velocity, list[int] of chord notes
    notePlayed = Signal(int, float, int, list)
    noteReleased = Signal()
    errorOccurred = Signal(str)
    recordingStateChanged = Signal(bool)
    recordingSaved = Signal(str, str, str)  # wav_path, midi_path, musicxml_path

    def __init__(
        self,
        soundfont_path: str,
        input_device: int | None = None,
        rms_threshold: float = 0.01,
        confidence: float = 0.3,
        note_hold_ms: int = 120,
        recordings_dir: str = "recordings",
        instrument_program: int = DEFAULT_INSTRUMENT_PROGRAM,
        chord_mode: str = DEFAULT_CHORD,
        key_label: str = DEFAULT_KEY,
        bass_octaves: int = 0,
        dom7_on_v: bool = False,
    ) -> None:
        super().__init__()
        self._soundfont_path = soundfont_path
        self._input_device = input_device
        self._rms_threshold = rms_threshold
        self._confidence = confidence
        self._note_hold_ms = note_hold_ms
        self._recordings_dir = Path(recordings_dir)
        self._instrument_program = instrument_program
        self._chord_mode = chord_mode
        self._key_label = key_label
        self._key_tonic, self._key_mode = key_label_to_tonic(key_label)
        self._bass_octaves = bass_octaves
        self._dom7_on_v = dom7_on_v

        self._audio_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=20)
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._in_stream: sd.InputStream | None = None
        self._out_stream: sd.OutputStream | None = None
        self._fs: fluidsynth.Synth | None = None
        self._sfid: int | None = None
        self._root_note: int | None = None
        self._active_notes: set[int] = set()

        # recording state
        self._recording = False
        self._rec_lock = threading.Lock()
        self._wav_chunks: list[np.ndarray] = []  # int16 interleaved stereo
        self._midi_events: list[tuple[float, str, int, int]] = []
        self._rec_start_time = 0.0

    # --- public controls --------------------------------------------------

    def set_threshold(self, value: float) -> None:
        self._rms_threshold = float(value)

    def set_confidence(self, value: float) -> None:
        self._confidence = float(value)

    def set_instrument(self, program: int) -> None:
        self._instrument_program = int(program)
        if self._fs is not None and self._sfid is not None:
            self._fs.program_select(0, self._sfid, 0, self._instrument_program)

    def set_chord_mode(self, mode: str) -> None:
        if mode not in CHORD_RECIPES:
            return
        # Drop the in-flight chord so the next detection picks up the new mode.
        self._release_active_notes()
        self._chord_mode = mode

    def set_key(self, label: str) -> None:
        self._release_active_notes()
        self._key_label = label
        self._key_tonic, self._key_mode = key_label_to_tonic(label)

    def set_bass_octaves(self, n: int) -> None:
        self._release_active_notes()
        self._bass_octaves = max(0, int(n))

    def set_dom7_on_v(self, enabled: bool) -> None:
        self._release_active_notes()
        self._dom7_on_v = bool(enabled)

    def is_running(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        if self.is_running():
            return
        if not Path(self._soundfont_path).exists():
            self.errorOccurred.emit(f"SoundFont not found: {self._soundfont_path}")
            return

        try:
            self._fs = fluidsynth.Synth(samplerate=float(SAMPLE_RATE), gain=1.0)
            sfid = self._fs.sfload(self._soundfont_path)
            if sfid == -1:
                raise RuntimeError("FluidSynth could not load SoundFont")
            self._fs.program_select(0, sfid, 0, self._instrument_program)
            self._sfid = sfid
        except Exception as exc:
            self.errorOccurred.emit(f"FluidSynth init failed: {exc}")
            self._fs = None
            self._sfid = None
            return

        try:
            self._out_stream = sd.OutputStream(
                samplerate=SAMPLE_RATE,
                channels=2,
                dtype="float32",
                blocksize=OUTPUT_BLOCK,
                callback=self._output_callback,
            )
            self._out_stream.start()
        except Exception as exc:
            self.errorOccurred.emit(f"Output stream failed: {exc}")
            self._cleanup_synth()
            return

        try:
            self._in_stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                blocksize=BLOCK_SIZE,
                device=self._input_device,
                callback=self._input_callback,
            )
            self._in_stream.start()
        except Exception as exc:
            self.errorOccurred.emit(f"Mic open failed: {exc}")
            self._cleanup_streams()
            self._cleanup_synth()
            return

        self._stop_event.clear()
        self._worker = threading.Thread(target=self._run_worker, daemon=True)
        self._worker.start()

    def stop(self) -> None:
        if self._recording:
            self.stop_recording()
        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=2.0)
            self._worker = None
        self._cleanup_streams()
        self._cleanup_synth()
        self._root_note = None
        self._active_notes.clear()
        self.noteReleased.emit()

    def start_recording(self) -> None:
        if self._recording or not self.is_running():
            return
        with self._rec_lock:
            self._wav_chunks.clear()
            self._midi_events.clear()
            self._rec_start_time = time.monotonic()
            self._recording = True
        self.recordingStateChanged.emit(True)

    def stop_recording(self) -> tuple[str, str] | None:
        if not self._recording:
            return None
        with self._rec_lock:
            self._recording = False
            wav_chunks = self._wav_chunks
            midi_events = self._midi_events
            self._wav_chunks = []
            self._midi_events = []

        self.recordingStateChanged.emit(False)

        if not wav_chunks and not midi_events:
            return None

        self._recordings_dir.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        wav_path = self._recordings_dir / f"piano_{stamp}.wav"
        midi_path = self._recordings_dir / f"piano_{stamp}.mid"
        musicxml_path = self._recordings_dir / f"piano_{stamp}.musicxml"

        try:
            self._write_wav(wav_path, wav_chunks)
            self._write_midi(midi_path, midi_events)
        except Exception as exc:
            self.errorOccurred.emit(f"Save failed: {exc}")
            return None

        # MusicXML is best-effort: if quantization fails we still keep WAV+MIDI.
        xml_out = ""
        try:
            self._write_musicxml(midi_path, musicxml_path, self._key_label)
            xml_out = str(musicxml_path)
        except Exception as exc:
            self.errorOccurred.emit(f"MusicXML export failed (WAV+MIDI saved): {exc}")

        self.recordingSaved.emit(str(wav_path), str(midi_path), xml_out)
        return str(wav_path), str(midi_path), xml_out

    # --- callbacks --------------------------------------------------------

    def _input_callback(self, indata, frames, time_info, status):  # noqa: ARG002
        try:
            self._audio_q.put_nowait(indata[:, 0].copy())
        except queue.Full:
            pass

    def _output_callback(self, outdata, frames, time_info, status):  # noqa: ARG002
        if self._fs is None:
            outdata.fill(0.0)
            return
        samples = self._fs.get_samples(frames)  # int16 interleaved (2*frames,)
        if self._recording:
            with self._rec_lock:
                if self._recording:
                    self._wav_chunks.append(samples.copy())
        stereo = samples.reshape(-1, 2).astype(np.float32) / 32768.0
        outdata[:] = stereo

    # --- worker -----------------------------------------------------------

    def _run_worker(self) -> None:
        last_voiced = 0.0
        while not self._stop_event.is_set():
            try:
                frame = self._audio_q.get(timeout=0.1)
            except queue.Empty:
                continue

            rms = float(np.sqrt(np.mean(frame**2)))
            self.levelChanged.emit(rms)
            now = time.monotonic()

            if rms < self._rms_threshold:
                if (
                    self._root_note is not None
                    and now - last_voiced > self._note_hold_ms / 1000.0
                ):
                    self._release_active_notes()
                    self.noteReleased.emit()
                continue

            freq = detect_pitch_autocorr(
                frame, SAMPLE_RATE, confidence=self._confidence
            )
            if freq is None:
                continue

            midi = freq_to_midi(freq)
            if not (PIANO_MIN_MIDI <= midi <= PIANO_MAX_MIDI):
                continue

            velocity = int(np.clip(rms * 800, 40, 120))
            self._play_chord(midi, freq, velocity)
            last_voiced = now

    # --- note helpers -----------------------------------------------------

    def _play_chord(self, root: int, freq: float, velocity: int) -> None:
        if self._fs is None or self._root_note == root:
            return

        if self._chord_mode in DIATONIC_MODES:
            voices = diatonic_chord_notes(
                root,
                self._key_tonic,
                self._key_mode,
                use_seventh=self._chord_mode == "Diatonic 7th",
                bass_octaves=self._bass_octaves,
                dom7_on_V=self._dom7_on_v,
            )
        else:
            intervals = CHORD_RECIPES.get(self._chord_mode, (0,))
            voices = [root + i for i in intervals]
            if self._bass_octaves > 0 and 0 in intervals:
                # User has Bass slider on with a non-diatonic recipe — add it.
                for k in range(1, self._bass_octaves + 1):
                    voices.insert(0, root - 12 * k)

        new_notes = {n for n in voices if PIANO_MIN_MIDI <= n <= PIANO_MAX_MIDI}

        # Release notes that aren't in the new chord, keep shared ones ringing.
        for old in self._active_notes - new_notes:
            self._fs.noteoff(0, old)
            self._record_midi("off", old, 0)
        for new in new_notes - self._active_notes:
            self._fs.noteon(0, new, velocity)
            self._record_midi("on", new, velocity)

        self._active_notes = new_notes
        self._root_note = root
        self.notePlayed.emit(root, freq, velocity, sorted(new_notes))

    def _release_active_notes(self) -> None:
        if self._fs is None:
            self._active_notes.clear()
            self._root_note = None
            return
        for n in self._active_notes:
            self._fs.noteoff(0, n)
            self._record_midi("off", n, 0)
        self._active_notes.clear()
        self._root_note = None

    def _record_midi(self, kind: str, note: int, velocity: int) -> None:
        if not self._recording:
            return
        with self._rec_lock:
            if self._recording:
                t = time.monotonic() - self._rec_start_time
                self._midi_events.append((t, kind, note, velocity))

    # --- save -------------------------------------------------------------

    @staticmethod
    def _write_wav(path: Path, chunks: list[np.ndarray]) -> None:
        if not chunks:
            return
        data = np.concatenate(chunks)  # int16 interleaved L/R
        with wave.open(str(path), "wb") as f:
            f.setnchannels(2)
            f.setsampwidth(2)
            f.setframerate(SAMPLE_RATE)
            f.writeframes(data.tobytes())

    @staticmethod
    def _write_musicxml(midi_path: Path, xml_path: Path, key_label: str) -> None:
        # music21 is heavy; import lazily so app startup stays fast.
        import music21

        score = music21.converter.parse(str(midi_path))

        tonic = (
            key_label.replace(" major", "").replace(" minor", "").replace("b", "-")
        )
        mode = "minor" if "minor" in key_label else "major"
        try:
            score.insert(0, music21.key.Key(tonic, mode))
        except Exception:
            pass

        # Snap to 16th notes or 8th-note triplets.
        score.quantize(
            quarterLengthDivisors=(4, 3),
            processOffsets=True,
            processDurations=True,
            recurse=True,
            inPlace=True,
        )
        score.write("musicxml", fp=str(xml_path))

    @staticmethod
    def _write_midi(
        path: Path, events: list[tuple[float, str, int, int]]
    ) -> None:
        if not events:
            return
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)

        tempo = mido.bpm2tempo(120)
        ticks_per_beat = mid.ticks_per_beat
        track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
        track.append(mido.Message("program_change", program=0, time=0))

        last_t = 0.0
        for t, kind, note, velocity in events:
            delta_sec = max(0.0, t - last_t)
            delta_ticks = int(mido.second2tick(delta_sec, ticks_per_beat, tempo))
            msg_type = "note_on" if kind == "on" else "note_off"
            track.append(
                mido.Message(msg_type, note=note, velocity=velocity, time=delta_ticks)
            )
            last_t = t

        mid.save(str(path))

    # --- cleanup ----------------------------------------------------------

    def _cleanup_streams(self) -> None:
        for s in (self._in_stream, self._out_stream):
            if s is not None:
                try:
                    s.stop()
                    s.close()
                except Exception:
                    pass
        self._in_stream = None
        self._out_stream = None

    def _cleanup_synth(self) -> None:
        if self._fs is not None:
            try:
                for n in self._active_notes:
                    self._fs.noteoff(0, n)
                self._fs.delete()
            except Exception:
                pass
            self._fs = None
        self._sfid = None
        self._active_notes.clear()
