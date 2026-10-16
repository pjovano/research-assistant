from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import identifiers
import zotero

from _file.bib import BibEditor, RequiredFields
from _file.finder import FoundIdentifier, FoundIdentifiers, IdentifierFinder
from _file.normalize_record import Proposal, RecordNormalizer
from _file.notes import DraftCard
from _file.resolvers import (
    ArxivResolver,
    CrossrefResolver,
    IsbnResolver,
    LookupFailed,
    RequestsFetcher,
    Resolution,
)

STATUS_RESOLVED = "resolved"
STATUS_NO_IDENTIFIER = "no-identifier"
STATUS_LOOKUP_FAILED = "lookup-failed"
_ORIG_YEAR = "orig_year"
_RESOLUTION_ORDER = (identifiers.KIND_DOI, identifiers.KIND_ARXIV, identifiers.KIND_ISBN)


@dataclass(frozen=True)
class Lookup:
    status: str
    identifier: FoundIdentifier | None = None
    resolution: Resolution | None = None
    detail: str | None = None

    def as_dict(self) -> dict:
        return {"status": self.status,
                "identifier": self.identifier.as_dict() if self.identifier else None,
                "service": self.resolution.service if self.resolution else None,
                "detail": self.detail}


class IdentifierResolution:
    def __init__(self, fetcher) -> None:
        self._resolvers = {
            identifiers.KIND_DOI: CrossrefResolver(fetcher),
            identifiers.KIND_ARXIV: ArxivResolver(fetcher),
            identifiers.KIND_ISBN: IsbnResolver(fetcher),
        }

    def of(self, found: FoundIdentifiers) -> Lookup:
        chosen = next((item for item in map(found.first_of_kind, _RESOLUTION_ORDER) if item), None)
        if chosen is None:
            return Lookup(STATUS_NO_IDENTIFIER)
        try:
            return self._resolved(chosen)
        except LookupFailed as failure:
            return Lookup(STATUS_LOOKUP_FAILED, chosen, detail=str(failure))

    def _resolved(self, chosen: FoundIdentifier) -> Lookup:
        return Lookup(STATUS_RESOLVED, chosen, self._resolvers[chosen.kind].resolve(chosen.value))


class IdentifyReport:
    def __init__(self, pdf_path: Path, fetcher: RequestsFetcher | None = None) -> None:
        self._pdf_path = pdf_path
        self._fetcher = fetcher or RequestsFetcher()

    def render(self) -> dict:
        found = IdentifierFinder(self._pdf_path).found()
        lookup = IdentifierResolution(self._fetcher).of(found)
        proposal = self._proposal(lookup, found)
        return {
            "file": self._pdf_path.name,
            "identifiers": found.as_dicts(),
            "isbns_found": found.of_kind(identifiers.KIND_ISBN),
            "chapter_doi_evidence": found.chapter_doi_evidence(),
            "lookup": lookup.as_dict(),
            "proposal": proposal.fields,
            _ORIG_YEAR: proposal.orig_year,
            "missing_for_type": RequiredFields().missing(proposal.fields.get("itemType", ""), proposal.fields),
            "normalizations": proposal.normalizations,
            "flags": proposal.flags,
        }

    def write(self) -> dict:
        report = self.render()
        if report["lookup"]["status"] != STATUS_RESOLVED:
            return {**report, "written": [], "conflicts": []}
        writer = ProposalWriter(report)
        outcome = BibEditor(self._pdf_path).edit(writer.into)
        return {**report, "written": writer.written, "conflicts": writer.conflicts, "draft": outcome["draft"]}

    def _proposal(self, lookup: Lookup, found: FoundIdentifiers) -> Proposal:
        if lookup.resolution is None:
            return Proposal()
        return RecordNormalizer(lookup.resolution.record, found.of_kind(identifiers.KIND_ISBN)).proposal()


class ProposalWriter:
    def __init__(self, report: dict) -> None:
        self._report = report
        self.written: list[str] = []
        self.conflicts: list[dict] = []

    def into(self, draft: DraftCard) -> None:
        for name, value in self._report["proposal"].items():
            self._set_zotero_field(draft, name, value)
        self._set_orig_year(draft)
        draft.set_identified(self._provenance())

    def _set_zotero_field(self, draft: DraftCard, name: str, value: object) -> None:
        recorded = draft.zotero.get(name)
        if self._conflicting(recorded, value):
            self._note_conflict(name, recorded, value)
            return
        draft.set_zotero_field(name, value)
        self.written.append(name)

    def _set_orig_year(self, draft: DraftCard) -> None:
        proposed = self._report[_ORIG_YEAR]
        if not proposed:
            return
        if self._conflicting(draft.orig_year, proposed):
            self._note_conflict(_ORIG_YEAR, draft.orig_year, proposed)
            return
        draft.set_orig_year(proposed)
        self.written.append(_ORIG_YEAR)

    def _conflicting(self, recorded: object, proposed: object) -> bool:
        return recorded not in zotero.EMPTY_FIELD_VALUES and recorded != proposed

    def _note_conflict(self, name: str, recorded: object, proposed: object) -> None:
        self.conflicts.append({"field": name, "recorded": recorded, "proposed": proposed})

    def _provenance(self) -> dict:
        lookup = self._report["lookup"]
        return {
            "identifier": lookup["identifier"],
            "service": lookup["service"],
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "normalizations": list(self._report["normalizations"]),
            "flags": list(self._report["flags"]),
        }
