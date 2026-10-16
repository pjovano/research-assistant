from __future__ import annotations

from pathlib import Path

import pymupdf

from .crosspage import RequestResolver
from .editing import HighlightStamp, IncrementalEdit
from .notes import NoteLedger
from .requests import ADDED, MERGED, RECTANGLE, AnnotationDecision, AnnotationRequest, DecisionReport
from .resolver import DocumentWorkspaces, PageWorkspace


class AnnotationPlan:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path

    def decisions(self, requests: list[AnnotationRequest]) -> DecisionReport:
        with pymupdf.open(self._pdf_path) as document:
            resolver = RequestResolver(DocumentWorkspaces(document))
            resolved = [resolver.resolve(request) for request in requests]
        return DecisionReport(resolved)


class AnnotationWriter:
    def __init__(self, pdf_path: Path, author: str | None) -> None:
        self._pdf_path = pdf_path
        self._author = author
        self._report = DecisionReport([])

    @property
    def report(self) -> DecisionReport:
        return self._report

    def apply(self, requests: list[AnnotationRequest]) -> None:
        self._report = IncrementalEdit(self._pdf_path).applied(
            lambda document: self._write_all(document, requests), lambda report: report.writes)

    def _write_all(self, document, requests: list[AnnotationRequest]) -> DecisionReport:
        workspaces = DocumentWorkspaces(document)
        resolver = RequestResolver(workspaces)
        decisions = []
        for request in requests:
            decision = resolver.resolve(request)
            self._commit_halves(workspaces, decision)
            decisions.append(decision)
        return DecisionReport(decisions)

    def _commit_halves(self, workspaces: DocumentWorkspaces, decision: AnnotationDecision) -> None:
        for half in decision.halves:
            self._commit(workspaces.at(half.page), half)

    def _commit(self, workspace: PageWorkspace, decision: AnnotationDecision) -> None:
        if decision.action in (ADDED, RECTANGLE):
            self._add(workspace, decision)
        elif decision.action == MERGED:
            self._append_note(decision)

    def _add(self, workspace: PageWorkspace, decision: AnnotationDecision) -> None:
        annotation = workspace.page.add_highlight_annot(decision.quads)
        note = decision.request.note
        HighlightStamp(annotation).recoloured(decision.request.colour).stamped(
            self._author or "", note.rendered, note.tag.label)

    def _append_note(self, decision: AnnotationDecision) -> None:
        target = decision.target
        note = decision.request.note
        HighlightStamp(target).covering(decision.quads).stamped(target.info.get("title") or self._author or "",
                                       NoteLedger.of(target).appended(note),
                                       target.info.get("subject") or note.tag.label)
