"""Voice-to-piano GUI entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from voice_to_piano.ui import MainWindow


def main() -> None:
    parser = argparse.ArgumentParser(description="Voice-to-piano GUI")
    parser.add_argument(
        "--soundfont",
        "-sf",
        default=str(Path(__file__).parent / "soundfonts" / "GeneralUser.sf2"),
        help="Path to .sf2 SoundFont file",
    )
    args = parser.parse_args()

    sf_path = args.soundfont if Path(args.soundfont).exists() else None

    app = QApplication(sys.argv)
    window = MainWindow(soundfont_path=sf_path)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
