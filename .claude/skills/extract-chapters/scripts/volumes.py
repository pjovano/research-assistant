from __future__ import annotations

import sys
from pathlib import Path


def _lib_dir() -> Path:
    here = Path(__file__).resolve()
    return next(parent / "lib" for parent in here.parents if (parent / "lib" / "vault.py").is_file())


sys.path.insert(0, str(_lib_dir()))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _volumes.apparatus_ranges import ApparatusSection, VolumeApparatus
from _volumes.cli import CommandLine, main
from _volumes.contents import Chapter, ChapterTitle, HeldVolumes, VolumeContents
from _volumes.extraction import AppendedRange, ChapterExtraction, PageRange

__all__ = [
    "ApparatusSection", "AppendedRange", "Chapter", "ChapterExtraction", "ChapterTitle",
    "CommandLine", "HeldVolumes", "PageRange", "VolumeApparatus", "VolumeContents", "main",
]


if __name__ == "__main__":
    main()
