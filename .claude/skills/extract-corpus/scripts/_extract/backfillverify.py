from __future__ import annotations

import json
import math
import re
from pathlib import Path

from _extract.spans import ScopePoint

MISSING_HEADING = "missing heading"
LOG_EXCERPT_CHARS = 400
HEADING_MARK = "#"
WHITESPACE = re.compile(r"\s+")
PAGE_TOP_RANK = -1


def normalized_title(title: str) -> str:
    return WHITESPACE.sub(" ", title).strip().lower()


def missing_heading_finding(heading: dict) -> str:
    return f"{MISSING_HEADING}: {heading['title']!r} (file p. {heading['file_page']})"


def log_excerpt(entries) -> str:
    return json.dumps(entries, ensure_ascii=False)[:LOG_EXCERPT_CHARS]


class OutlinePlaces:
    def __init__(self, headings: list[dict]) -> None:
        self._headings = headings

    def of_heading(self, rank: int) -> tuple[float, int]:
        return self._headings[rank]["file_page"], rank

    def of_point(self, text: str) -> tuple[float, int]:
        point = ScopePoint.parsed(text)
        if point.is_end:
            return math.inf, PAGE_TOP_RANK
        return point.file_page, self._rank_named_by(point)

    def _rank_named_by(self, point: ScopePoint) -> int:
        opening = normalized_title(point.opening or "").split()
        return next((rank for rank, heading in enumerate(self._headings)
                     if heading["file_page"] == point.file_page and _one_opens_the_other(opening, heading)),
                    PAGE_TOP_RANK)


def _one_opens_the_other(opening: list[str], heading: dict) -> bool:
    title = normalized_title(heading["title"]).split()
    shorter = min(len(opening), len(title))
    return shorter > 0 and opening[:shorter] == title[:shorter]


class TrialVerification:
    def __init__(self, headings: list[dict], excluded_spans: list[tuple[str, str]]) -> None:
        self._headings = headings
        self._places = OutlinePlaces(headings)
        self._excluded_places = [(self._places.of_point(start), self._places.of_point(resume))
                                 for start, resume in excluded_spans]

    def findings(self, report: dict) -> list[str]:
        missing = [missing_heading_finding(heading) for heading in self.missing_headings(report)]
        return missing + self._log_findings(report)

    def missing_headings(self, report: dict) -> list[dict]:
        trial_text = Path(report["written"]).read_text()
        lines = [line.lstrip(HEADING_MARK).strip().lower() for line in trial_text.splitlines()
                 if line.startswith(HEADING_MARK)]
        missing, cursor = [], 0
        for heading in self._content_headings():
            title = normalized_title(heading["title"])
            hit = next((number for number in range(cursor, len(lines)) if title in lines[number]), None)
            if hit is None:
                missing.append({"title": heading["title"], "file_page": heading["file_page"]})
            else:
                cursor = hit + 1
        return missing

    def _content_headings(self) -> list[dict]:
        return [heading for rank, heading in enumerate(self._headings)
                if not self._is_excluded(self._places.of_heading(rank))]

    def _is_excluded(self, place: tuple[float, int]) -> bool:
        return any(start <= place < resume for start, resume in self._excluded_places)

    def _log_findings(self, report: dict) -> list[str]:
        flagged = [entry for entry in report.get("notation_log", []) if "flag" in json.dumps(entry)]
        logs = (("notation flagged", flagged), ("folio_log", report.get("folio_log")),
                ("footnote_log", report.get("footnote_log")))
        return [f"{label}: {log_excerpt(entries)}" for label, entries in logs if entries]
