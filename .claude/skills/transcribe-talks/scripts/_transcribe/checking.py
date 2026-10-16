from __future__ import annotations

import json
import re

from vault import HEADING_RE

from .listing import Part, ReviewListing
from .raw import TranscriptText
from .talk import TalkEntry

MIN_KEPT_RATIO = 0.5
REQUIRED_CARD_FIELDS = ("title", "presenters", "year", "meeting", "dropped")
SURNAME_FIELD = "lastName"
VERDICT_PASSED = "passed"
VERDICT_FAILED = "failed"
_MACHINE_LABEL_RE = re.compile(r"\bSPEAKER_(?:\d+|UNKNOWN)\b")
_ENCODING = "utf-8"


class TalkCard:
    def __init__(self, entry: TalkEntry) -> None:
        self._path = entry.card

    def problems(self) -> list[str]:
        if not self._path.exists():
            return [f"card missing: {self._path}"]
        try:
            fields = json.loads(self._path.read_text(encoding=_ENCODING))
        except ValueError as error:
            return [f"card is not JSON: {error}"]
        return self._field_problems(fields)

    def fields(self) -> dict:
        return json.loads(self._path.read_text(encoding=_ENCODING))

    def _field_problems(self, fields: dict) -> list[str]:
        missing = [f"card lacks {name}" for name in REQUIRED_CARD_FIELDS if name not in fields]
        return missing + self._presenter_problems(fields.get("presenters")) + self._year_problems(fields.get("year"))

    @staticmethod
    def _presenter_problems(presenters) -> list[str]:
        if not isinstance(presenters, list) or not presenters:
            return ["card names no presenter"]
        return [f"presenter {position} lacks a {SURNAME_FIELD}" for position, presenter in enumerate(presenters, 1)
                if not isinstance(presenter, dict) or not str(presenter.get(SURNAME_FIELD, "")).strip()]

    @staticmethod
    def _year_problems(year) -> list[str]:
        return [] if isinstance(year, int) else ["card year is not an integer"]


class ReviewedPart:
    def __init__(self, entry: TalkEntry, part: Part) -> None:
        self._path = entry.part_path(part.number)
        self._part = part

    def problems(self) -> list[str]:
        if not self._path.exists():
            return [f"part {self._part.number} missing: {self._path}"]
        text = self._path.read_text(encoding=_ENCODING)
        return self._marker_problems(text) + self._length_problems(text) + self._label_problems(text)

    def has_heading(self) -> bool:
        if not self._path.exists():
            return False
        return any(HEADING_RE.match(line) for line in self._path.read_text(encoding=_ENCODING).splitlines())

    def _marker_problems(self, text: str) -> list[str]:
        known = set(self._part.markers)
        found = [paragraph.time for paragraph in TranscriptText.paragraphs(text) if paragraph.time]
        return [f"part {self._part.number} carries a time marker the raw transcript lacks: {time}"
                for time in found if time not in known]

    def _length_problems(self, text: str) -> list[str]:
        kept = len(text.split())
        heard = self._part.heard_words
        if kept >= heard * MIN_KEPT_RATIO:
            return []
        return [f"part {self._part.number} keeps {kept} words of {heard} heard; a review drops chatter, "
                f"never the talk"]

    def _label_problems(self, text: str) -> list[str]:
        return [f"part {self._part.number} leaves a machine speaker label: {label}"
                for label in sorted(set(_MACHINE_LABEL_RE.findall(text)))]


class ReviewCheck:
    def __init__(self, entry: TalkEntry) -> None:
        self._entry = entry
        self._listing = ReviewListing(entry)
        self._parts = [ReviewedPart(entry, part) for part in self._listing.parts()]

    def report(self) -> dict:
        problems = (TalkCard(self._entry).problems() + self._part_problems() + self._unlisted_part_problems()
                    + self._heading_problems())
        verdict = VERDICT_FAILED if problems else VERDICT_PASSED
        return {"video_id": self._entry.video_id, "verdict": verdict, "parts": len(self._parts), "problems": problems}

    def _part_problems(self) -> list[str]:
        return [problem for part in self._parts for problem in part.problems()]

    def _unlisted_part_problems(self) -> list[str]:
        listed = set(self._listing.reviewed_paths())
        return [f"{path} is no part of the listing; delete it, or run review-listing and review again"
                for path in self._entry.reviewed_parts() if path not in listed]

    def _heading_problems(self) -> list[str]:
        if any(part.has_heading() for part in self._parts):
            return []
        return ["no reviewed part carries a heading; the review opens the talk and the discussion with one each"]
