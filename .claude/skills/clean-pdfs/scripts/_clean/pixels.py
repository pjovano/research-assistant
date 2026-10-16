from __future__ import annotations

import difflib
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import accents
from confusables import compatible

import vault

from .lines import Glyph, TextLine, TextLines
from .ocr import EngineReader, EngineReadings, VisionReader
from .sampling import spread
from .textkey import TextLayerCacheEntry, TextLayerDigest, TextLayerKey

SAMPLES_PER_GLYPH = 3
MIN_SAMPLES = 2
MAX_AGREEMENT_RATIO = 0.1
MIN_READING_SHARE = 0.5
CACHE_NAME = vault.PIXELS_CACHE_NAME
CHECK_VERSION = 8
OPERATION_EQUAL = "equal"
OPERATION_REPLACE = "replace"
OPERATION_DELETE = "delete"


@dataclass(frozen=True)
class Reading:
    glyph: Glyph
    read: str | None

    def agrees(self) -> bool:
        return self.read is not None and self.read == self.glyph.folded()


class LineComparison:
    def __init__(self, line: TextLine, ocr_text: str) -> None:
        self._glyphs = [glyph for glyph in line.glyphs() if not glyph.is_blank()]
        self._layer = [glyph.folded() for glyph in self._glyphs]
        self._read = [compatible(char) for char in ocr_text if not char.isspace()]

    def readings(self) -> list[Reading]:
        matcher = difflib.SequenceMatcher(a=self._layer, b=self._read, autojunk=False)
        readings: list[Reading] = []
        for operation, a0, a1, b0, b1 in matcher.get_opcodes():
            readings.extend(self._readings_of(operation, self._glyphs[a0:a1], self._read[b0:b1]))
        return readings

    def counted_readings(self, counted: Callable[[Glyph], bool]) -> list[Reading]:
        return [reading for reading in self.readings() if counted(reading.glyph)]

    def _readings_of(self, operation: str, glyphs: list[Glyph], read: list[str]) -> list[Reading]:
        if operation == OPERATION_EQUAL or self._spells_the_same(glyphs, read):
            return [Reading(glyph, glyph.folded()) for glyph in glyphs]
        if operation == OPERATION_REPLACE and len(glyphs) == len(read):
            return [Reading(glyph, char) for glyph, char in zip(glyphs, read)]
        if operation in (OPERATION_REPLACE, OPERATION_DELETE):
            return [Reading(glyph, None) for glyph in glyphs]
        return []

    @staticmethod
    def _spells_the_same(glyphs: list[Glyph], read: list[str]) -> bool:
        drawn = accents.composed_either_side("".join(glyph.char for glyph in glyphs))
        return bool(glyphs) and compatible(drawn) == "".join(read)


@dataclass(frozen=True)
class Disagreement:
    font: str
    char: str
    samples: int
    agreements: int
    reading: str | None

    @property
    def glyph(self) -> Glyph:
        return Glyph(self.font, self.char)

    def as_dict(self) -> dict:
        return {"font": self.font, "char": self.char, "samples": self.samples, "agreements": self.agreements,
                "reading": self.reading}

    @staticmethod
    def from_dict(row: dict) -> "Disagreement":
        return Disagreement(row["font"], row["char"], int(row["samples"]), int(row["agreements"]), row.get("reading"))


class GlyphVerdicts:
    def __init__(self) -> None:
        self._agreements: Counter = Counter()
        self._readings: dict[Glyph, Counter] = {}

    def add_all(self, readings: list[Reading]) -> None:
        for reading in readings:
            self._add(reading)

    def glyph_count(self) -> int:
        return len(self._readings)

    def disagreements(self) -> list[Disagreement]:
        found = [self._disagreement(glyph, readings) for glyph, readings in self._readings.items()]
        return sorted((entry for entry in found if entry is not None), key=lambda entry: (entry.font, entry.char))

    def _add(self, reading: Reading) -> None:
        readings = self._readings.setdefault(reading.glyph, Counter())
        if reading.agrees():
            self._agreements[reading.glyph] += 1
        else:
            readings[reading.read] += 1

    def _disagreement(self, glyph: Glyph, readings: Counter) -> Disagreement | None:
        agreements = self._agreements[glyph]
        samples = agreements + sum(readings.values())
        if samples < MIN_SAMPLES or agreements > samples * MAX_AGREEMENT_RATIO:
            return None
        return Disagreement(glyph.font, glyph.char, samples, agreements, self._dominant(readings))

    @staticmethod
    def _dominant(readings: Counter) -> str | None:
        named = Counter({read: count for read, count in readings.items() if read is not None})
        if not named:
            return None
        read, count = named.most_common(1)[0]
        return read if count >= sum(readings.values()) * MIN_READING_SHARE else None


class LineSample:
    def __init__(self, lines: list[TextLine], wanted: Callable[[Glyph], bool],
                 per_glyph: int = SAMPLES_PER_GLYPH) -> None:
        self._lines = lines
        self._wanted = wanted
        self._per_glyph = per_glyph

    def chosen(self) -> list[TextLine]:
        chosen: set[int] = set()
        for indexes in self._indexes_by_glyph().values():
            chosen.update(spread(indexes, self._per_glyph))
        return [self._lines[index] for index in sorted(chosen)]

    def _indexes_by_glyph(self) -> dict[Glyph, list[int]]:
        by_glyph: dict[Glyph, list[int]] = {}
        for index, line in enumerate(self._lines):
            for glyph in line.distinct_glyphs():
                if self._wanted(glyph):
                    by_glyph.setdefault(glyph, []).append(index)
        return by_glyph


@dataclass(frozen=True)
class PixelResult:
    lines_read: int
    glyphs_checked: int
    disagreements: list[Disagreement]
    unread_sheets: int = 0

    def is_complete(self) -> bool:
        return self.unread_sheets == 0

    def as_dict(self) -> dict:
        return {"lines_read": self.lines_read, "glyphs_checked": self.glyphs_checked,
                "unread_sheets": self.unread_sheets,
                "disagreements": [entry.as_dict() for entry in self.disagreements]}

    @staticmethod
    def from_dict(payload: dict) -> "PixelResult":
        return PixelResult(int(payload["lines_read"]), int(payload["glyphs_checked"]),
                           [Disagreement.from_dict(row) for row in payload["disagreements"]],
                           int(payload["unread_sheets"]))

    @staticmethod
    def empty() -> "PixelResult":
        return PixelResult(0, 0, [])


class PixelCache:
    def __init__(self, pdf_path: Path, digest: TextLayerDigest | None = None) -> None:
        key = TextLayerKey(digest or TextLayerDigest(pdf_path), [CHECK_VERSION])
        self._entry = TextLayerCacheEntry(pdf_path, CACHE_NAME, key)

    def load(self) -> PixelResult | None:
        payload = self._entry.load()
        return None if payload is None else PixelResult.from_dict(payload)

    def save(self, result: PixelResult) -> None:
        self._entry.save(result.as_dict())


@dataclass(frozen=True)
class LineReaders:
    vision: VisionReader
    engine: EngineReader

    @classmethod
    def of(cls, pdf_path: Path) -> "LineReaders":
        return cls(VisionReader(pdf_path), EngineReader(pdf_path))


class PixelCheck:
    def __init__(self, pdf_path: Path, readers: LineReaders | None = None, cache: PixelCache | None = None) -> None:
        self._path = pdf_path
        self._readers = readers or LineReaders.of(pdf_path)
        self._cache = cache or PixelCache(pdf_path)

    def result(self) -> PixelResult:
        cached = self._cache.load()
        if cached is not None:
            return cached
        result = self._checked()
        self._save_if_complete(result)
        return result

    def _save_if_complete(self, result: PixelResult) -> None:
        if result.is_complete():
            self._cache.save(result)

    def _checked(self) -> PixelResult:
        lines = TextLines(self._path).collect()
        plain_lines = LineSample(lines, Glyph.is_plain).chosen()
        symbol_lines = LineSample(lines, Glyph.is_symbol).chosen()
        verdicts = GlyphVerdicts()
        self._compare(verdicts, self._readers.vision.read(plain_lines), Glyph.is_plain)
        engine = self._engine_readings(symbol_lines)
        self._compare(verdicts, engine.readings, self._every_glyph)
        lines_read = len(plain_lines) + len(symbol_lines)
        return PixelResult(lines_read, verdicts.glyph_count(), verdicts.disagreements(), engine.unread_sheets)

    def _engine_readings(self, lines: list[TextLine]) -> EngineReadings:
        if not lines:
            return EngineReadings.none()
        return self._readers.engine.read(lines)

    @staticmethod
    def _every_glyph(glyph: Glyph) -> bool:
        return True

    @staticmethod
    def _compare(verdicts: GlyphVerdicts, readings: list[tuple[TextLine, str | None]], counted) -> None:
        for line, text in readings:
            if text is not None:
                verdicts.add_all(LineComparison(line, text).counted_readings(counted))


class PixelChecks:
    def result(self, pdf_path: Path, digest: TextLayerDigest) -> PixelResult:
        return PixelCheck(pdf_path, cache=PixelCache(pdf_path, digest)).result()
