from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

import pagetext
import vault

from .document import VolumeDocument

NO_FOLIO = "no printed folio"
RETAINED_TEXT_RATIO = 0.9
PARTIAL_SUFFIX = ".partial"

_RANGE_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")


class PageRange:
    def __init__(self, first: int, last: int) -> None:
        if first < 1 or last < first:
            raise ValueError(f"file pages {first}-{last}: pages are 1-based and first <= last")
        self.first = first
        self.last = last

    @classmethod
    def parse(cls, text: str) -> PageRange:
        hit = _RANGE_RE.match(text)
        if not hit:
            raise ValueError(f"'{text}' is not a file-page range of the form <first>-<last>")
        return cls(int(hit.group(1)), int(hit.group(2)))

    @property
    def count(self) -> int:
        return self.last - self.first + 1

    def zero_based(self) -> tuple[int, int]:
        return self.first - 1, self.last - 1

    def indices(self) -> list[int]:
        return list(range(self.first - 1, self.last))


class AppendedRange:
    def __init__(self, label: str, page_range: PageRange) -> None:
        self.label = label
        self.page_range = page_range

    def as_json(self) -> dict:
        return {"label": self.label,
                "file_pages": f"{self.page_range.first}-{self.page_range.last}",
                "page_count": self.page_range.count}


@dataclass(frozen=True)
class ChosenChapter:
    page_range: PageRange
    title: str
    appended: tuple[AppendedRange, ...] = ()


class ChapterExtraction:
    def __init__(self, volume: VolumeDocument, chosen: ChosenChapter) -> None:
        self._volume = volume
        self._source = volume.pdf
        self._range = chosen.page_range
        self._appended = list(chosen.appended)
        self._dest = vault.INBOX_DIR / f"{vault.sanitize_filename_part(chosen.title)}.pdf"

    def plan(self) -> dict:
        self._reject_bad_range()
        folios = RangeFolios(self._source, self._range)
        return {"source": str(self._source),
                "file_pages": f"{self._range.first}-{self._range.last}",
                "printed_folios": f"{folios.first()}-{folios.last()}",
                "appended": [item.as_json() for item in self._appended],
                "page_count": self._total_count(),
                "dest": str(self._dest)}

    def _ranges(self) -> list[PageRange]:
        return [self._range] + [item.page_range for item in self._appended]

    def _total_count(self) -> int:
        return sum(page_range.count for page_range in self._ranges())

    def _all_indices(self) -> list[int]:
        return [index for page_range in self._ranges() for index in page_range.indices()]

    @property
    def destination(self) -> Path:
        return self._dest

    def write(self) -> None:
        self._reject_bad_range()
        self._reject_existing_dest()
        vault.INBOX_DIR.mkdir(parents=True, exist_ok=True)
        self._copy_ranges()
        ExtractionCheck(self._source, self._dest, self._all_indices()).run()

    def _copy_ranges(self) -> None:
        with pymupdf.open(self._source) as source, pymupdf.open() as chapter, \
                vault.ReplacementFile(self._dest, PARTIAL_SUFFIX) as replacement:
            for page_range in self._ranges():
                first, last = page_range.zero_based()
                chapter.insert_pdf(source, from_page=first, to_page=last)
            chapter.set_toc([])
            chapter.save(replacement.path)
            replacement.commit()

    def _reject_bad_range(self) -> None:
        pages = self._volume.page_count
        for page_range in self._ranges():
            if page_range.last > pages:
                raise ValueError(f"{self._source.name} has {pages} pages; file pages "
                                 f"{page_range.first}-{page_range.last} run past the end.")

    def _reject_existing_dest(self) -> None:
        if self._dest.exists():
            raise ValueError(f"{self._dest.name} is already in the inbox; this command never "
                             "overwrites. Delete it first or pass a different --title.")


class RangeFolios:
    def __init__(self, source: Path, page_range: PageRange) -> None:
        records = pagetext.page_records(source, limit=page_range.count, start=page_range.first - 1)
        self._labels = [record.printed_page for record in records]

    def first(self) -> str:
        return self._at(0)

    def last(self) -> str:
        return self._at(-1)

    def _at(self, index: int) -> str:
        if not self._labels:
            return NO_FOLIO
        return self._labels[index] or NO_FOLIO


class ExtractionCheck:
    def __init__(self, source: Path, dest: Path, source_indices: list[int]) -> None:
        self._source = source
        self._dest = dest
        self._expected_pages = len(source_indices)
        self._source_indices = source_indices

    def run(self) -> None:
        self._check_page_count()
        self._check_text_retained()

    def _check_page_count(self) -> None:
        written = VolumeDocument.read(self._dest).page_count
        if written != self._expected_pages:
            self._reject(f"wrote {written} pages, not the {self._expected_pages} requested")

    def _check_text_retained(self) -> None:
        before = self._text_length(self._source, self._source_indices)
        after = self._text_length(self._dest, list(range(self._expected_pages)))
        if before and after < before * RETAINED_TEXT_RATIO:
            self._reject(f"text collapsed from {before} to {after} characters")

    @staticmethod
    def _text_length(path: Path, indices: list[int]) -> int:
        texts = dict(pagetext.page_texts(path))
        return sum(len(texts[index + 1].strip()) for index in indices)

    def _reject(self, reason: str) -> None:
        self._dest.unlink(missing_ok=True)
        raise ValueError(f"Refusing to keep {self._dest.name}: {reason}.")
