from __future__ import annotations

import vault
from references import CitationParser, CitationScoring, HeldWorks, LibraryWork

from _cite.linking import EntryLinker, LinkedLine, LinkResolution, LinkTargets, NoteLines
from _cite.verdicts import CitationVerdicts

STATUS_UNCHANGED = "unchanged"
STATUS_CHANGED = "changed"
STATUS_REWRITTEN = "rewritten"
STATUS_NO_BODY = "no-body"
STATUS_NO_PDF = "no-pdf"


class NoteBody:
    def __init__(self, note: vault.GuardedNote) -> None:
        self._note = note

    def text(self) -> str:
        return vault.split_note(self._note.text())[1]


class ConflictCopies:
    def names(self) -> list[str]:
        return vault.library_conflict_copies()


class LinkWriter:
    def __init__(self, note: vault.GuardedNote) -> None:
        self._note = note

    def write(self, links: list[LinkedLine]) -> None:
        frontmatter, body = vault.split_note(self._note.text())
        lines = body.split("\n")
        for link in links:
            lines[link.index] = link.text
        self._note.replace(vault.join_note(frontmatter, "\n".join(lines)))


class NoteLinks:
    def __init__(self, basename: str, scoring: CitationScoring, verdicts: CitationVerdicts | None = None) -> None:
        self._basename = basename
        self._scoring = scoring
        self._verdicts = verdicts or CitationVerdicts()
        self._citing = scoring.held.find(basename)
        self._path = vault.corpus_path(basename)
        self._note = vault.GuardedNote(self._path)
        self._body = NoteBody(self._note)

    def status(self) -> dict:
        return self._blocked() or self._row_for(self._resolution(), STATUS_CHANGED)

    def apply(self) -> dict:
        blocked = self._blocked()
        if blocked:
            return blocked
        resolution = self._resolution()
        if resolution.links:
            LinkWriter(self._note).write(resolution.links)
        return self._row_for(resolution, STATUS_REWRITTEN)

    def resolution(self) -> LinkResolution:
        return LinkResolution([], []) if self._blocked() else self._resolution()

    def _row_for(self, resolution: LinkResolution, status_with_links: str) -> dict:
        return self._row(status_with_links if resolution.links else STATUS_UNCHANGED, resolution)

    def _blocked(self) -> dict | None:
        if self._citing is None:
            return self._row(STATUS_NO_PDF, LinkResolution([], []))
        if not self._has_body():
            return self._row(STATUS_NO_BODY, LinkResolution([], []))
        return None

    def _has_body(self) -> bool:
        return self._path.exists() and bool(vault.body_after_pdf_link(self._body.text()).strip())

    def _resolution(self) -> LinkResolution:
        linker = EntryLinker(self._scoring.for_citing(self._citing), LinkTargets(), self._verdicts.of(self._basename))
        return linker.resolve(NoteLines(self._body.text()))

    def _row(self, status: str, resolution: LinkResolution) -> dict:
        return {"basename": self._basename, "status": status, "links_to_add": len(resolution.links),
                "linked_works": sorted({link.basename for link in resolution.links}),
                "to_confirm": [line.as_dict() for line in resolution.to_confirm],
                "stale": [line.as_dict() for line in resolution.stale]}


class CitersOf:
    def __init__(self, cited: LibraryWork) -> None:
        self._cited = cited

    def basenames(self) -> list[str]:
        return [vault.basename_of(path) for path in vault.list_corpus_files() if self._may_cite(path)]

    def _may_cite(self, path) -> bool:
        if vault.basename_of(path) == self._cited.basename:
            return False
        lowered = path.read_text(encoding="utf-8").lower()
        return any(surname in lowered for surname in self._cited.surname_tokens)


class LinksRebuild:
    def __init__(self, basenames: list[str], parser: CitationParser | None = None,
                 verdicts: CitationVerdicts | None = None) -> None:
        self._held = HeldWorks.from_library()
        self._basenames = [vault.nfc(name) for name in basenames or self._corpus_basenames()]
        self._scoring = CitationScoring(self._held, parser or CitationParser())
        self._verdicts = verdicts or CitationVerdicts()

    @classmethod
    def citing(cls, cited_basename: str, parser: CitationParser | None = None) -> LinksRebuild:
        cited = HeldWorks.from_library().find(cited_basename)
        if cited is None:
            raise LookupError(f"'{cited_basename}' is not a held work: no PDF of that basename is in the library")
        return cls(CitersOf(cited).basenames() or [cited_basename], parser)

    @staticmethod
    def _corpus_basenames() -> list[str]:
        return [vault.basename_of(path) for path in vault.list_corpus_files()]

    def status(self) -> list[dict]:
        return [self._links(basename).status() for basename in self._basenames]

    def apply(self) -> list[dict]:
        return [self._links(basename).apply() for basename in self._basenames]

    def resolutions(self) -> dict[str, LinkResolution]:
        return {basename: self._links(basename).resolution() for basename in self._basenames}

    def _links(self, basename: str) -> NoteLinks:
        return NoteLinks(basename, self._scoring, self._verdicts)
