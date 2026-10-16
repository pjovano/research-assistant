from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from .cmap import ZERO_WIDTH_SPACE
from .fonts import FontRecord
from .glyphs import METHOD_GLYPH_NAME, GlyphQuery, Identity, IdentityResolver, is_suspect, unicode_label
from .lines import Glyph
from .pixels import Disagreement
from .textlayer import Occurrences, SuspectOccurrence

MISSING_FROM_TOUNICODE = "missing-from-tounicode"
SOURCE_RULES = "rules"
SOURCE_PIXELS = "pixels"


@dataclass(frozen=True)
class FlaggedCode:
    record: FontRecord
    code: str
    char: str
    identity: Identity | None
    source: str = SOURCE_RULES
    reading: str | None = None

    @property
    def glyph_name(self) -> str | None:
        return self.record.glyph_name(self.code)

    @property
    def text_layer_glyph(self) -> Glyph:
        return Glyph(self.record.text_layer_name, self.char)

    def is_resolved(self) -> bool:
        return self.identity is not None

    def is_confirmed(self) -> bool:
        return self.identity is not None and (self.identity.unicode or ZERO_WIDTH_SPACE) == self.char

    def identity_key(self) -> tuple[str, str, str]:
        return self.record.family, self.glyph_name or self.code, self.char

    def location(self) -> dict:
        return {**_font_location(self.record), "code": self.code}

    def as_row(self, count: int) -> dict:
        return {**self.location(), "unicode": unicode_label(self.char), "glyph_name": self.glyph_name,
                "count": count, "identity": self.identity.unicode if self.identity else None,
                "method": self.identity.method if self.identity else None, "source": self.source,
                "reading": self.reading}

    def as_record(self) -> dict:
        return {"font": self.record.family, "code": self.code, "old": unicode_label(self.char),
                "new": self.identity.unicode, "method": self.identity.method}


class FontStatusRows:
    def __init__(self, record: FontRecord, found: list[SuspectOccurrence]) -> None:
        self._record = record
        self._found = found

    def rows(self) -> list[dict]:
        if not self._found:
            return []
        if self._record.status:
            return [{**_font_location(self._record), "status": self._record.status}]
        return [self._missing_row(char, count) for char, count in sorted(self._unexplained().items())]

    def disagreement_row(self, disagreement: Disagreement) -> dict:
        return {**self._missing_row(disagreement.char, disagreement.samples), "reading": disagreement.reading}

    def _unexplained(self) -> Counter:
        return Counter(found.char for found in self._found if not self._is_traced(found.char))

    def _is_traced(self, char: str) -> bool:
        return self._record.maps_to(char) or bool(self._record.codes_for(char))

    def _missing_row(self, char: str, count: int) -> dict:
        return {**_font_location(self._record), "status": MISSING_FROM_TOUNICODE, "unicode": unicode_label(char),
                "count": count}


class FontRows:
    def __init__(self, status_rows: list[dict], disagreement_rows: list[dict]) -> None:
        self._status_rows = status_rows
        self._disagreement_rows = disagreement_rows

    def rows(self) -> list[dict]:
        unreported = [row for row in self._disagreement_rows if not self._is_reported(row)]
        return [self._with_reading(row) for row in self._status_rows] + unreported

    def _is_reported(self, disagreement_row: dict) -> bool:
        return any(_names_same_character(row, disagreement_row) for row in self._status_rows)

    def _with_reading(self, status_row: dict) -> dict:
        readings = [row["reading"] for row in self._disagreement_rows if _names_same_character(status_row, row)]
        return {**status_row, "reading": readings[0]} if readings else status_row


def _is_used(flagged: FlaggedCode, occurrences: Occurrences) -> bool:
    if not occurrences.gathers(flagged.record, flagged.char):
        return True
    return bool(occurrences.of(flagged.record, flagged.char))


def _settled_by_glyph_name(record: FontRecord, code: str, char: str) -> Identity | None:
    return Identity(char, METHOD_GLYPH_NAME) if record.glyph_name_names(code, char) else None


def _names_same_character(status_row: dict, disagreement_row: dict) -> bool:
    return status_row["font"] == disagreement_row["font"] and status_row.get("unicode") == disagreement_row["unicode"]


def _font_location(record: FontRecord) -> dict:
    return {"font": record.family, "subset": record.basefont, "xref": record.xref}


@dataclass(frozen=True)
class ScanInput:
    path: Path
    records: list[FontRecord]
    disagreements: Sequence[Disagreement] = ()
    occurrences: Occurrences | None = None


class FontScan:
    def __init__(self, scanned: ScanInput, resolver: IdentityResolver) -> None:
        self._path = scanned.path
        self._resolver = resolver
        self._records = [record for record in scanned.records if not record.ocr_layer]
        self._disagreements = scanned.disagreements
        self._occurrences = scanned.occurrences
        self._flagged: list[FlaggedCode] | None = None
        self._uncoded: list[Disagreement] = []

    def flagged(self) -> list[FlaggedCode]:
        return list(self._flags())

    def used(self, occurrences: Occurrences) -> list[FlaggedCode]:
        return [flagged for flagged in self._flags() if _is_used(flagged, occurrences)]

    def summary(self) -> dict:
        return self._summary(self._flags())

    def flagged_file_pages(self, occurrences: Occurrences) -> list[int] | None:
        flags = self._flags()
        if self._uncoded or not all(occurrences.gathers(flagged.record, flagged.char) for flagged in flags):
            return None
        return sorted({found.page_number for flagged in flags for found in occurrences.of(flagged.record, flagged.char)})

    def report(self, occurrences: Occurrences) -> dict:
        counted = [(flagged, len(occurrences.of(flagged.record, flagged.char))) for flagged in self._flags()]
        used = [flagged for flagged, _ in counted if _is_used(flagged, occurrences)]
        codes = [flagged.as_row(count) for flagged, count in counted]
        fonts = FontRows(self._status_rows(occurrences), self._uncoded_rows()).rows()
        return {**self._summary(used), "codes_unused": len(counted) - len(used), "codes": codes, "fonts": fonts}

    def _status_rows(self, occurrences: Occurrences) -> list[dict]:
        return [row for record in self._records for row in FontStatusRows(record, occurrences.of_font(record)).rows()]

    def _flags(self) -> list[FlaggedCode]:
        if self._flagged is None:
            self._scan()
        return self._flagged

    def _scan(self) -> None:
        self._flagged = [self._flag(record, code, char)
                         for record in self._records for code, char in record.flagged_codes()]
        if self._occurrences is not None:
            self._flag_emitted_suspects(self._occurrences)
        for disagreement in self._disagreements:
            self._flag_disagreement(disagreement)

    def _summary(self, considered: list[FlaggedCode]) -> dict:
        return {"pdf": self._path.name,
                "fonts_flagged": len({flagged.record.xref for flagged in self._flags()}),
                "codes_flagged": len(self._flags()),
                "codes_unresolved": sum(1 for flagged in considered if not flagged.is_resolved())}

    def _flag(self, record: FontRecord, code: str, char: str) -> FlaggedCode:
        return FlaggedCode(record, code, char, self._identity(record, code, char))

    def _flag_from_pixels(self, record: FontRecord, code: str, disagreement: Disagreement) -> FlaggedCode:
        char = disagreement.char
        identity = self._identity(record, code, char) or _settled_by_glyph_name(record, code, char)
        return FlaggedCode(record, code, char, identity, SOURCE_PIXELS, disagreement.reading)

    def _identity(self, record: FontRecord, code: str, char: str) -> Identity | None:
        return self._resolver.resolve(GlyphQuery(record.family, record.glyph_name(code), code, char))

    def _flag_emitted_suspects(self, occurrences: Occurrences) -> None:
        for record in self._records:
            if record.emits_its_codes:
                self._flag_emitted_by(record, occurrences)

    def _flag_emitted_by(self, record: FontRecord, occurrences: Occurrences) -> None:
        emitted = {found.char for found in occurrences.of_font(record) if is_suspect(found.char)}
        coded = ((code, char) for char in sorted(emitted) for code in record.codes_for(char))
        self._flagged.extend(self._flag(record, code, char) for code, char in coded
                             if not self._is_flagged(record, code))

    def _is_flagged(self, record: FontRecord, code: str) -> bool:
        return self._flagged_position(record, code) is not None

    def _flagged_position(self, record: FontRecord, code: str) -> int | None:
        positions = (position for position, flagged in enumerate(self._flagged)
                     if flagged.record.xref == record.xref and flagged.code == code)
        return next(positions, None)

    def _flag_disagreement(self, disagreement: Disagreement) -> None:
        coded = [(record, code) for record in self._records_named(disagreement.font)
                 for code in record.codes_for(disagreement.char)]
        if not coded:
            self._uncoded.append(disagreement)
        for record, code in coded:
            self._flag_disagreeing_code(record, code, disagreement)

    def _flag_disagreeing_code(self, record: FontRecord, code: str, disagreement: Disagreement) -> None:
        position = self._flagged_position(record, code)
        if position is None:
            self._flagged.append(self._flag_from_pixels(record, code, disagreement))
        else:
            self._flagged[position] = replace(self._flagged[position], reading=disagreement.reading)

    def _records_named(self, font: str) -> list[FontRecord]:
        return [record for record in self._records if record.text_layer_name == font]

    def _uncoded_rows(self) -> list[dict]:
        rows = (self._uncoded_row(disagreement) for disagreement in self._uncoded)
        return [row for row in rows if row is not None]

    def _uncoded_row(self, disagreement: Disagreement) -> dict | None:
        record = next(iter(self._records_named(disagreement.font)), None)
        return None if record is None else FontStatusRows(record, []).disagreement_row(disagreement)
