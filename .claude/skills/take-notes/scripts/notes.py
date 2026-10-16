from __future__ import annotations

import sys
from pathlib import Path


def _lib_dir() -> Path:
    here = Path(__file__).resolve()
    return next(parent / "lib" for parent in here.parents if (parent / "lib" / "vault.py").is_file())


sys.path.insert(0, str(_lib_dir()))

from _writing.notes_cli import NotesCommandLine, main

__all__ = ["NotesCommandLine", "main"]


if __name__ == "__main__":
    main()
