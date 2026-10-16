from __future__ import annotations

import sys
from pathlib import Path


def _lib_dir() -> Path:
    here = Path(__file__).resolve()
    return next(parent / "lib" for parent in here.parents if (parent / "lib" / "vault.py").is_file())


sys.path.insert(0, str(_lib_dir()))

from _bibliographies.cli import EXIT_ALREADY_CLASSIFIED, EXIT_REPEATED_WORK_LIST, ChangeSet, CommandLine, main
from _bibliographies.diagnostics import (
    AUTHORS_FOLDER,
    REISSUES_HEADING,
    WORKS_FOR_AN_AUTHOR_BIBLIOGRAPHY,
    AuthorChecks,
    ClassificationChecks,
    ConflictCopyChecks,
    ListingChecks,
    PlacementChecks,
    Report,
    ReportBuilder,
    TreeChecks,
)
from _bibliographies.tree import BibliographyTree
from _bibliographies.notes import (
    MAPS_HEADING,
    Bibliographies,
    Bibliography,
    BibliographyNotFound,
    Corpus,
    CorpusNote,
    NoteChange,
    NoteNotFound,
    Writing,
)
from _bibliographies.opening import Classification, NoteSections, Opening
from _bibliographies.placement import RepeatedWorkList, WorkList, WorkPlacement
from _bibliographies.sections import Section

__all__ = [
    "AUTHORS_FOLDER", "EXIT_ALREADY_CLASSIFIED", "EXIT_REPEATED_WORK_LIST", "REISSUES_HEADING",
    "WORKS_FOR_AN_AUTHOR_BIBLIOGRAPHY",
    "AuthorChecks",
    "Bibliographies", "Bibliography", "BibliographyNotFound", "BibliographyTree",
    "ChangeSet", "Classification", "ClassificationChecks", "CommandLine", "ConflictCopyChecks", "Corpus",
    "CorpusNote", "ListingChecks", "NoteChange", "NoteNotFound", "NoteSections", "Opening", "PlacementChecks",
    "MAPS_HEADING", "RepeatedWorkList", "Report", "ReportBuilder", "Section", "TreeChecks",
    "WorkList", "WorkPlacement", "Writing", "main",
]


if __name__ == "__main__":
    main()
