"""Command-line entry point for the MemPalace mapping simulator."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.mempalace.dialogue_alignment import main


if __name__ == "__main__":
    raise SystemExit(main())
