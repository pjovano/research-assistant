from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from _extract.console import FORCE_OCR_FLAG
from _extract.failures import UsageFailure

SCOPE_FIELD = "extraction_scope"
FLAGS_FIELD = "extraction_flags"
REVIEWED_FIELD = "extraction_reviewed"
EXTRACTION_MODE_FIELD = "extraction_mode"
FORCE_OCR_PAGES_FLAG = "--force-ocr-pages"
SPAN_SEPARATOR = " ⇢ "
SPAN_PARTS = 2
STORED_SCOPE_KEY = "scope"
STORED_FLAGS_KEY = "flags"
CLEARED_RECORD_FIELDS = {SCOPE_FIELD: None, FLAGS_FIELD: None, REVIEWED_FIELD: None, EXTRACTION_MODE_FIELD: None}


class RecordUnreadable(UsageFailure, ValueError):
    pass


@dataclass(frozen=True)
class ExtractionRequest:
    excluded: tuple[tuple[str, str], ...] | None
    force_ocr: bool = False
    forced_pages: str | None = None
    fresh: bool = False
    readings_path: Path | None = None
    cache_only: bool = False

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> ExtractionRequest:
        readings = Path(args.readings) if args.readings else None
        return cls(cls._excluded_of(args), args.force_ocr, args.force_ocr_pages, args.fresh, readings)

    @staticmethod
    def _excluded_of(args: argparse.Namespace) -> tuple[tuple[str, str], ...] | None:
        if args.exclude is None and not args.exclude_nothing:
            return None
        return tuple((start, resume) for start, resume in args.exclude or [])

    @classmethod
    def from_record(cls, meta: dict, basename: str) -> ExtractionRequest:
        record = _RecordedFields(meta, basename)
        return cls._recorded(record.excluded(), record.flags())

    @classmethod
    def from_stored(cls, stored: dict, basename: str) -> ExtractionRequest:
        return cls._recorded(_stored_spans(stored, basename),
                             [str(flag) for flag in stored.get(STORED_FLAGS_KEY) or []])

    @classmethod
    def _recorded(cls, excluded: tuple[tuple[str, str], ...], flags: list[str]) -> ExtractionRequest:
        forced_pages = flags[flags.index(FORCE_OCR_PAGES_FLAG) + 1] if FORCE_OCR_PAGES_FLAG in flags else None
        return cls(excluded, FORCE_OCR_FLAG in flags, forced_pages)

    @property
    def scope_given(self) -> bool:
        return self.excluded is not None

    def record_fields(self) -> dict:
        spans = [quoted(SPAN_SEPARATOR.join(span)) for span in self.excluded or ()]
        return {SCOPE_FIELD: spans, FLAGS_FIELD: [quoted(flag) for flag in self._flags()]}

    def stored(self) -> dict:
        return {STORED_SCOPE_KEY: [list(span) for span in self.excluded or ()], STORED_FLAGS_KEY: self._flags()}

    def _flags(self) -> list[str]:
        flags = [FORCE_OCR_FLAG] if self.force_ocr else []
        if self.forced_pages:
            flags += [FORCE_OCR_PAGES_FLAG, self.forced_pages]
        return flags


def _stored_spans(stored: dict, basename: str) -> tuple[tuple[str, str], ...]:
    spans = stored.get(STORED_SCOPE_KEY)
    if not isinstance(spans, list) or not all(isinstance(span, list) and len(span) == SPAN_PARTS for span in spans):
        raise RecordUnreadable(f"{basename} has a malformed extraction record: {stored!r}")
    return tuple((str(start), str(resume)) for start, resume in spans)


def quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


class _RecordedFields:
    def __init__(self, meta: dict, basename: str) -> None:
        self._meta = meta
        self._basename = basename

    def excluded(self) -> tuple[tuple[str, str], ...]:
        spans = self._meta.get(SCOPE_FIELD)
        if not isinstance(spans, list):
            raise RecordUnreadable(f"{self._basename} records no {SCOPE_FIELD}; only an accepted work is rebuilt")
        return tuple(self._span(str(span)) for span in spans)

    def _span(self, recorded: str) -> tuple[str, str]:
        parts = recorded.split(SPAN_SEPARATOR)
        if len(parts) != SPAN_PARTS:
            raise RecordUnreadable(f"{self._basename} records a malformed span in {SCOPE_FIELD}: {recorded!r}")
        return parts[0], parts[1]

    def flags(self) -> list[str]:
        return [str(flag) for flag in self._meta.get(FLAGS_FIELD) or []]
