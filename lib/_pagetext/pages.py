from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

import accents
import vault
from text_layer_spaces import ZeroAdvanceSpaces

from _pagetext.folio import FolioResolver, PageInput

TOP_LEVEL = 1
DEFAULT_RENDER_DPI = 150
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")
_MARKUP_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9]*(?:\s[^<>]*)?/?>")


@dataclass
class PageRecord:
    pdf_page: int
    printed_page: str | None
    text: str


def document_fingerprint(pdf_path: Path) -> tuple:
    stat = Path(pdf_path).stat()
    return (str(Path(pdf_path).resolve()), stat.st_mtime_ns, stat.st_size)


class PdfPages:
    def __init__(self) -> None:
        self._fingerprint: tuple | None = None
        self._records: list[PageRecord] = []

    def records(self, pdf_path: Path) -> list[PageRecord]:
        fingerprint = document_fingerprint(pdf_path)
        if fingerprint != self._fingerprint:
            self._records = self._read(pdf_path)
            self._fingerprint = fingerprint
        return self._records

    def segment(self, pdf_path: Path, start: int, limit: int | None) -> list[PageRecord]:
        records = self.records(pdf_path)
        last = len(records) if limit is None else min(len(records), start + limit)
        return records[start:last]

    def texts(self, pdf_path: Path, start: int, limit: int | None) -> list[tuple[int, str]]:
        return [(record.pdf_page, record.text) for record in self.segment(pdf_path, start, limit)]

    def printed_label(self, pdf_path: Path, pdf_page: int) -> str | None:
        if pdf_page < 1:
            return None
        records = self.segment(pdf_path, pdf_page - 1, 1)
        return records[0].printed_page if records else None

    def _read(self, pdf_path: Path) -> list[PageRecord]:
        with pymupdf.open(pdf_path) as doc:
            inputs = [self._page_input(doc[index]) for index in range(doc.page_count)]
        folios = FolioResolver().resolve(inputs)
        return [PageRecord(index + 1, folios[index], inputs[index].text) for index in range(len(inputs))]

    def _page_input(self, page) -> PageInput:
        text = ZeroAdvanceSpaces(page).closed(accents.composed(page.get_text() or ""))
        return PageInput(text, self._raw_label(page))

    @staticmethod
    def _raw_label(page) -> str | None:
        try:
            return page.get_label() or None
        except (AttributeError, IndexError):
            return None


class PdfOutline:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path

    def entries(self) -> list[tuple[int, str, int]]:
        with pymupdf.open(self._pdf_path) as doc:
            return [self._entry(level, title, page) for level, title, page in (doc.get_toc() or [])]

    @staticmethod
    def _entry(level, title, page) -> tuple[int, str, int]:
        return int(level), outline_title(str(title)), int(page)


def outline_title(raw: str) -> str:
    unmarked = html.unescape(_MARKUP_TAG_RE.sub("", raw))
    title = _CONTROL_CHARS_RE.sub("", _WHITESPACE_RE.sub(" ", unmarked)).strip()
    return _past_a_truncated_copy(title)


def _past_a_truncated_copy(title: str) -> str:
    restart = next((start for start in range(1, len(title))
                    if _is_cut_inside_a_word(title[:start]) and title[start:].startswith(title[:start])), None)
    return title if restart is None else title[restart:]


def _is_cut_inside_a_word(opening: str) -> bool:
    return " " in opening and not opening[-1].isspace()


class PageRenderer:
    def __init__(self, pdf_path: Path, dpi: int = DEFAULT_RENDER_DPI) -> None:
        self._pdf_path = pdf_path
        self._dpi = dpi

    def rendered(self, pages: list[int]) -> list[Path]:
        directory = vault.SCRATCH_DIR / self._pdf_path.stem
        directory.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(self._pdf_path) as doc:
            renders = [self._render(doc, number, directory) for number in pages]
        return [path for path in renders if path is not None]

    def _render(self, doc, number: int, directory: Path) -> Path | None:
        if number < 1 or number > doc.page_count:
            return None
        dest = directory / vault.RENDER_NAME.format(number=number)
        doc[number - 1].get_pixmap(dpi=self._dpi).save(dest)
        return dest


PDF_PAGES = PdfPages()


class PdfPageReading:
    @staticmethod
    def page_records(pdf_path: Path, *, limit: int | None = None, start: int = 0) -> list[PageRecord]:
        return PDF_PAGES.segment(Path(pdf_path), start, limit)

    @staticmethod
    def page_texts(pdf_path: Path, *, limit: int | None = None, start: int = 0) -> list[tuple[int, str]]:
        return PDF_PAGES.texts(Path(pdf_path), start, limit)

    @staticmethod
    def printed_page_label(pdf_path: Path, pdf_page: int) -> str | None:
        return PDF_PAGES.printed_label(Path(pdf_path), pdf_page)

    @staticmethod
    def outline_entries(pdf_path: Path) -> list[tuple[int, str, int]]:
        return PdfOutline(Path(pdf_path)).entries()

    @staticmethod
    def render_pages(pdf_path: Path, pages: list[int], *, dpi: int = DEFAULT_RENDER_DPI) -> list[Path]:
        return PageRenderer(Path(pdf_path), dpi).rendered(pages)


page_records = PdfPageReading.page_records
page_texts = PdfPageReading.page_texts
printed_page_label = PdfPageReading.printed_page_label
outline_entries = PdfPageReading.outline_entries
render_pages = PdfPageReading.render_pages
