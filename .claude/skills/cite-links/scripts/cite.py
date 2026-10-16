from __future__ import annotations

import sys
from pathlib import Path


def _lib_dir() -> Path:
    here = Path(__file__).resolve()
    return next(parent / "lib" for parent in here.parents if (parent / "lib" / "vault.py").is_file())


sys.path.insert(0, str(_lib_dir()))

from _cite.cli import CommandLine
from _cite.linking import ConfirmableLine, EntryLinker, LinkedLine, LinkResolution, NoteLines
from _cite.rebuild import (
    STATUS_CHANGED,
    STATUS_NO_BODY,
    STATUS_NO_PDF,
    STATUS_REWRITTEN,
    STATUS_UNCHANGED,
    ConflictCopies,
    LinksRebuild,
    NoteLinks,
)
from _cite.settle import (
    STATUS_NOT_OFFERED,
    STATUS_PLANNED,
    STATUS_RECORDED,
    RebuildFactory,
    RunGate,
    RunLockHeld,
    ScoreBand,
    Settlement,
    VerdictsFile,
    VerdictsFileUnreadable,
)
from _cite.verdicts import CONFIRM, REJECT, CitationVerdicts, Verdict, VerdictsFileCorrupt

__all__ = [
    "CONFIRM", "REJECT", "STATUS_CHANGED", "STATUS_NO_BODY", "STATUS_NO_PDF", "STATUS_NOT_OFFERED", "STATUS_PLANNED",
    "STATUS_RECORDED", "STATUS_REWRITTEN", "STATUS_UNCHANGED", "CitationVerdicts", "CommandLine", "ConfirmableLine",
    "ConflictCopies", "EntryLinker", "LinkResolution", "LinkedLine", "LinksRebuild", "NoteLines", "NoteLinks",
    "RebuildFactory", "RunGate", "RunLockHeld", "ScoreBand", "Settlement", "Verdict", "VerdictsFile", "VerdictsFileCorrupt",
    "VerdictsFileUnreadable",
]


if __name__ == "__main__":
    CommandLine().run(sys.argv[1:])
