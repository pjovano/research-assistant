from __future__ import annotations

import sys
from pathlib import Path


def _lib_dir() -> Path:
    here = Path(__file__).resolve()
    return next(parent / "lib" for parent in here.parents if (parent / "lib" / "vault.py").is_file())


sys.path.insert(0, str(_lib_dir()))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _file.bib import (
    REQUIRED_BIB_FIELDS,
    Assignment,
    BibEditor,
    BibReport,
    MetadataMerge,
    RequiredFields,
)
from _file.notes import (
    HAND_WRITTEN_FIELDS,
    UNCITABLE_FIELD,
    UNCITABLE_TOKEN,
    CorpusNote,
    DraftCard,
    NoteFrontmatter,
    UncitableField,
)
from _file.citekeys import CitekeyAllocator
from _file.cli import CommandLine, Commands, main
from _file.finder import FoundIdentifier, FoundIdentifiers, IdentifierFinder
from _file.identify import (
    STATUS_LOOKUP_FAILED,
    STATUS_NO_IDENTIFIER,
    STATUS_RESOLVED,
    IdentifyReport,
    ProposalWriter,
)
from _file.normalize_record import Proposal, RecordNormalizer
from _file.resolvers import (
    ArxivResolver,
    CrossrefResolver,
    Fetched,
    IsbnResolver,
    LookupFailed,
    RequestsFetcher,
    Resolution,
)
from _file.filing import (
    ATTACH_SETTLE_SECONDS,
    AssignedCitekey,
    AttachmentWatcher,
    Filer,
    FilingAttempt,
    FilingCompletion,
    FilingOutcome,
    ItemFiler,
    PlacedAttachment,
    Placement,
    ZoteroHolding,
)
from _file.paths import NotePaths, PdfLocator
from _file.preview import UNDATED_YEAR, FilingPreview
from _file.probe import (
    JOURNAL_ARTICLE_PAGE_THRESHOLD,
    AuthorByline,
    AuthorNames,
    OpeningPagesDump,
    PdfProbe,
)
from _file.refile import Refiler, RefileTarget
from _file.relink import Relinker, RelinkReport, RelinkRow
from _file.retry import STATUS_ZOTERO_STILL_OFFLINE, PendingDrafts, RetryRunner
from _file.status import DoctorReport, StatusReport

__all__ = [
    "STATUS_LOOKUP_FAILED", "STATUS_NO_IDENTIFIER", "STATUS_RESOLVED", "ArxivResolver", "CrossrefResolver",
    "Fetched", "FoundIdentifier", "FoundIdentifiers", "IdentifierFinder", "IdentifyReport", "IsbnResolver",
    "LookupFailed", "Proposal", "ProposalWriter", "RecordNormalizer", "RequestsFetcher", "Resolution",
    "ATTACH_SETTLE_SECONDS", "HAND_WRITTEN_FIELDS", "JOURNAL_ARTICLE_PAGE_THRESHOLD", "REQUIRED_BIB_FIELDS",
    "STATUS_ZOTERO_STILL_OFFLINE", "UNDATED_YEAR",
    "UNCITABLE_FIELD", "UNCITABLE_TOKEN", "AssignedCitekey", "Assignment", "AttachmentWatcher", "AuthorByline",
    "AuthorNames", "BibEditor", "BibReport", "CitekeyAllocator",
    "CommandLine", "Commands", "CorpusNote", "DoctorReport", "DraftCard", "Filer", "FilingAttempt",
    "FilingCompletion", "FilingOutcome", "FilingPreview",
    "ItemFiler", "MetadataMerge", "NoteFrontmatter", "NotePaths", "OpeningPagesDump", "PdfLocator",
    "PdfProbe", "PendingDrafts", "PlacedAttachment", "Placement",
    "Refiler", "RefileTarget",
    "RelinkReport", "RelinkRow", "Relinker", "RequiredFields", "RetryRunner",
    "StatusReport", "UncitableField", "ZoteroHolding", "main",
]


if __name__ == "__main__":
    main()
