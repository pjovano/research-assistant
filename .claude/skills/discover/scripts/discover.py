from __future__ import annotations

import sys
from pathlib import Path


def _lib_dir() -> Path:
    here = Path(__file__).resolve()
    return next(parent / "lib" for parent in here.parents if (parent / "lib" / "vault.py").is_file())


sys.path.insert(0, str(_lib_dir()))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _discover.cited import CitedEntry, Locator, UnheldEntries, UnheldWork, UnheldWorks
from _discover.cli import CommandLine
from _discover.matching import CitationMatch, EditionIdentity, Record, RecordMatch
from _discover.merging import (
    Candidate, CandidateMerge, CandidateParser, HeldMarking, LocalCitations, MergeReport, Ordering, UnseenKnownItems,
)

__all__ = [
    "Candidate", "CandidateMerge", "CandidateParser", "CitationMatch", "CitedEntry", "CommandLine", "EditionIdentity",
    "HeldMarking",
    "LocalCitations", "Locator", "MergeReport", "Ordering", "Record", "RecordMatch", "UnheldEntries", "UnheldWork",
    "UnheldWorks", "UnseenKnownItems",
]


if __name__ == "__main__":
    CommandLine().run(sys.argv[1:])
