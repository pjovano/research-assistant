from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import vault
from _annotate.notes import OMISSION

from .notation_restoration import QuotationWording

VERIFY_SCRIPT = Path(__file__).resolve().parents[2] / ".claude" / "skills" / "answer-questions" / "scripts" / "verify.py"
TIME_MARKER_RE = re.compile(r"%% (\d{2}:\d{2}:\d{2}) %%")
RECORDING_RE = re.compile(r"\[Recording\]\((?P<url>[^)]+)\)")
FOLIO_UNVERIFIED = "(folio unverified)"
FOLIO_PREFIX = "p. "
BENEATH_QUOTATION = "> \t"


@dataclass(frozen=True)
class QuotationRequest:
    source: str
    quotation: str
    locator: str | None = None


@dataclass(frozen=True)
class VerifiedQuotation:
    source: str
    wording: str
    locator: str
    link: str | None = None
    notation_to_read: tuple[str, ...] = ()
    file_page: int | None = None

    @property
    def source_line(self) -> str:
        locator = f"[{self.locator}]({self.link})" if self.link else self.locator
        return f"{BENEATH_QUOTATION}[[{self.source}]], {locator}"


class PdfVerification:
    def __init__(self, script: Path = VERIFY_SCRIPT) -> None:
        self._script = script

    def payload(self, request: QuotationRequest) -> dict:
        command = [sys.executable, str(self._script), "verify", request.source, request.quotation, "--json"]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError:
            raise ValueError(f"verify gave no verdict on {request.source!r}: "
                             f"{(completed.stderr or completed.stdout).strip()}") from None


class PdfQuotation:
    def __init__(self, verification: PdfVerification) -> None:
        self._verification = verification

    def verified(self, request: QuotationRequest) -> VerifiedQuotation:
        payload = self._verification.payload(request)
        if payload.get("ambiguous"):
            raise ValueError(f"the quotation appears on more than one page of {request.source!r}: quote a longer span")
        if not payload.get("verified"):
            raise ValueError(self._refusal(request, payload.get("hits") or []))
        hit = payload["hits"][0]
        notation = tuple(payload.get("notation_read_from_page") or ())
        wording = QuotationWording(request.quotation, hit["page_text"], notation).written()
        return VerifiedQuotation(request.source, wording, self._locator(hit), hit.get("link"), notation, hit.get("pdf_page"))

    @staticmethod
    def _locator(hit: dict) -> str:
        return f"p. {hit['printed_page']}" if hit.get("printed_page") else f"file p. {hit['pdf_page']}"

    @staticmethod
    def _refusal(request: QuotationRequest, hits: list[dict]) -> str:
        if not hits:
            return f"verify finds the quotation on no page of {request.source!r}: no reference is written"
        return (f"verify does not confirm the quotation in {request.source!r}: file p. {hits[0]['pdf_page']} reads "
                f"{hits[0]['page_text']!r}; quote the page's words")


class TranscriptQuotation:
    def __init__(self, transcript: Path) -> None:
        self._text = transcript.read_text(encoding="utf-8")

    def verified(self, request: QuotationRequest) -> VerifiedQuotation:
        hits = list(self._pattern(request.quotation).finditer(self._text))
        if len(hits) != 1:
            raise ValueError(f"the transcript {request.source!r} carries the quotation {len(hits)} times, not once: "
                             "quote its words exactly, in a span long enough to be the only one")
        return VerifiedQuotation(request.source, " ".join(hits[0].group(0).split()), self._time_before(hits[0].start()),
                                 self._recording())

    @staticmethod
    def _pattern(quotation: str) -> re.Pattern:
        return re.compile(r"\s+".join(re.escape(word) for word in quotation.split()))

    def _time_before(self, position: int) -> str:
        markers = TIME_MARKER_RE.findall(self._text[:position])
        if not markers:
            raise ValueError("no time marker precedes the passage in the transcript")
        return markers[-1]

    def _recording(self) -> str | None:
        hit = RECORDING_RE.search(self._text)
        return hit.group("url") if hit else None


class UncitableQuotation:
    def __init__(self, corpus_file: Path) -> None:
        self._meta = vault.parse_note(corpus_file.read_text(encoding="utf-8"))[0]

    def verified(self, request: QuotationRequest) -> VerifiedQuotation:
        if not self._meta.get(vault.UNCITABLE_FIELD):
            raise ValueError(f"{request.source!r} carries no uncitable: field: its quotation is verified, "
                             "and takes no locator")
        return VerifiedQuotation(request.source, request.quotation.strip(), f"{request.locator} {FOLIO_UNVERIFIED}")


class HeldQuotations:
    def __init__(self, verification: PdfVerification) -> None:
        self._verification = verification

    def verified(self, request: QuotationRequest) -> VerifiedQuotation:
        transcript = vault.transcript_path(request.source)
        corpus_file = vault.corpus_path(request.source)
        if transcript.is_file():
            return TranscriptQuotation(transcript).verified(request)
        if not corpus_file.is_file():
            raise ValueError(f"no corpus file or transcript named {request.source!r}: an unheld work takes a task")
        if request.locator:
            return UncitableQuotation(corpus_file).verified(request)
        return PdfQuotation(self._verification).verified(request)


class CompoundQuotation:
    def __init__(self, held: HeldQuotations) -> None:
        self._held = held

    def verified(self, request: QuotationRequest) -> VerifiedQuotation:
        passages = [part.strip() for part in request.quotation.split(OMISSION.strip()) if part.strip()]
        parts = [self._held.verified(QuotationRequest(request.source, passage, request.locator)) for passage in passages]
        if len(parts) == 1:
            return parts[0]
        self._require_one_stretch(request.source, parts)
        return VerifiedQuotation(request.source, OMISSION.join(part.wording for part in parts), self._locator(parts),
                                 parts[0].link,
                                 tuple(span for part in parts for span in part.notation_to_read), parts[0].file_page)

    @staticmethod
    def _require_one_stretch(source: str, parts: list[VerifiedQuotation]) -> None:
        pages = [part.file_page for part in parts]
        if None in pages or pages != sorted(pages) or pages[-1] - pages[0] > 1:
            raise ValueError(f"the passages of one reference stand in the page's order on one page of {source!r}, or run "
                             "on to the next: write a passage of another page as a reference of its own")

    @staticmethod
    def _locator(parts: list[VerifiedQuotation]) -> str:
        first, last = parts[0].locator, parts[-1].locator
        if first == last or not (first.startswith(FOLIO_PREFIX) and last.startswith(FOLIO_PREFIX)):
            return first
        return f"pp. {first.removeprefix(FOLIO_PREFIX)}–{last.removeprefix(FOLIO_PREFIX)}"

