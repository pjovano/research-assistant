from __future__ import annotations

import re
from dataclasses import dataclass, replace
from functools import cached_property
from pathlib import Path

import pikepdf
import pymupdf
from confusables import compatible

from .cmap import HEX_RADIX, ONE_BYTE_HEX_WIDTH, CMapError, ToUnicodeCMap, hex_code
from .glyphs import REPLACEMENT_CHARACTER, SURROGATES, GlyphName, is_suspect
from .lines import Glyph

SUBSET_PREFIX_RE = re.compile(r"^[A-Z]{6}\+")
BASE_ENCODING_KEY = "/BaseEncoding"
ENCODING_CODECS = {"WinAnsiEncoding": "cp1252", "MacRomanEncoding": "mac_roman"}
SINGLE_BYTE = 1
MUPDF_FONT_NAME_LIMIT = 31
SIMPLE_CODE_LIMIT = 0xFF
NAME_PREFIX = "/"
BASEFONT_KEY = "/BaseFont"
ENCODING_KEY = "/Encoding"
DIFFERENCES_KEY = "/Differences"
TOUNICODE_KEY = "/ToUnicode"
SUBTYPE_KEY = "/Subtype"
DESCENDANT_FONTS_KEY = "/DescendantFonts"
WIDTHS_KEY = "/Widths"
FIRST_CHAR_KEY = "/FirstChar"
TYPE0_SUBTYPE = "Type0"
IDENTITY_ENCODINGS = frozenset({"Identity-H", "Identity-V"})
NO_TOUNICODE = "no-tounicode"
UNPARSABLE_TOUNICODE = "tounicode-unparsable"
FIRST_GENERATION = 0
FIRST_DESCENDANT = 0
XREF_FIELD = 0
NO_XREF = 0
UNKNOWN_GLYPH_NAME = 0xFFFD
INVISIBLE_TEXT_TYPE = 3
FULL_PAGE_IMAGE_COVERAGE = 0.9
READ_FAILURES = (pikepdf.PdfError, RuntimeError, ValueError)


class FontReadError(RuntimeError):
    pass


def family_of(basefont: str) -> str:
    return SUBSET_PREFIX_RE.sub("", basefont)


def name_text(name: object) -> str:
    return str(name).lstrip(NAME_PREFIX)


class SimpleEncoding:
    def __init__(self, name: str | None) -> None:
        self._codec = ENCODING_CODECS.get(name or "")

    def code_for(self, char: str) -> str | None:
        if len(char) != 1:
            return None
        return self._encoded_code(char) if self._codec else self._code_point(char)

    def _encoded_code(self, char: str) -> str | None:
        try:
            encoded = char.encode(self._codec)
        except UnicodeEncodeError:
            return None
        return hex_code(encoded[0], ONE_BYTE_HEX_WIDTH) if len(encoded) == SINGLE_BYTE else None

    def _code_point(self, char: str) -> str | None:
        if ord(char) > SIMPLE_CODE_LIMIT:
            return None
        return hex_code(ord(char), ONE_BYTE_HEX_WIDTH)

    def char_for(self, code: str) -> str | None:
        byte = int(code, HEX_RADIX)
        return self._decoded(byte) if self._codec else chr(byte)

    def _decoded(self, byte: int) -> str | None:
        try:
            return bytes([byte]).decode(self._codec)
        except UnicodeDecodeError:
            return None


@dataclass(frozen=True)
class FontKey:
    family: str
    encoding: str | None


def glyph_name_char(name: str) -> str | None:
    code_point = pymupdf.mupdf.fz_unicode_from_glyph_name(name)
    return None if code_point == UNKNOWN_GLYPH_NAME else chr(code_point)


def parse_differences(items: list) -> dict[str, str]:
    names: dict[str, str] = {}
    code = 0
    for item in items:
        code = _name_or_reposition(names, item, code)
    return names


def _name_or_reposition(names: dict[str, str], item: object, code: int) -> int:
    if not isinstance(item, pikepdf.Name):
        return int(item)
    names[hex_code(code, ONE_BYTE_HEX_WIDTH)] = name_text(item)
    return code + 1


@dataclass(frozen=True)
class CidFont:
    basefont: str
    identity_encoded: bool

    def emitted(self, code: str, target: str) -> str:
        if self._emits_its_code(code, target):
            return chr(int(code, HEX_RADIX))
        return target

    def _emits_its_code(self, code: str, target: str) -> bool:
        return self.identity_encoded and target == REPLACEMENT_CHARACTER and int(code, HEX_RADIX) not in SURROGATES


@dataclass(frozen=True)
class FontRecord:
    xref: int
    basefont: str
    pages: frozenset[int]
    glyph_names: dict[str, str]
    cmap: ToUnicodeCMap | None
    status: str | None
    cid_font: CidFont | None = None
    encoding: str | None = None
    ocr_layer: bool = False
    drawn_codes: frozenset[str] = frozenset()

    @property
    def family(self) -> str:
        return family_of(self.basefont)

    @property
    def key(self) -> FontKey:
        return FontKey(self.family, self.encoding)

    @property
    def text_layer_name(self) -> str:
        named = self.cid_font.basefont if self.cid_font is not None else self.basefont
        return family_of(named[:MUPDF_FONT_NAME_LIMIT])

    def glyph_name(self, code: str) -> str | None:
        return self.glyph_names.get(code)

    def uses_page(self, page: int) -> bool:
        return page in self.pages

    def maps_to(self, char: str) -> bool:
        return char in self._emitted_characters

    def codes_for(self, char: str) -> list[str]:
        if self.cmap is not None:
            return (self._stand_in_codes_for(char) or self._mapped_codes_for(char)
                    or self._named_codes_for(char) or self._unmapped_codes_for(char))
        if self.glyph_names:
            return self._named_codes_for(char)
        return self._codes_emitted_as(char)

    def _named_codes_for(self, char: str) -> list[str]:
        mapped = {code for code, _, _ in self._mapping_rows}
        return [code for code, name in self.glyph_names.items()
                if code not in mapped and glyph_name_char(name) == char]

    @property
    def emits_its_codes(self) -> bool:
        return self.cmap is None and not self.glyph_names

    def stand_in_glyphs(self) -> set[Glyph]:
        return {Glyph(self.text_layer_name, emitted) for _, target, emitted in self._mapping_rows if emitted != target}

    def glyphs_emitted_beyond(self, overridden: set[str]) -> set[Glyph]:
        listed = {code for code, _, _ in self._mapping_rows} | set(self.glyph_names)
        emitted_by_listed = {Glyph(self.text_layer_name, emitted) for code in listed - overridden
                             if (emitted := self.emitted_at(code))}
        return emitted_by_listed | self._glyphs_of_drawn_codes_beyond(listed | overridden)

    def _glyphs_of_drawn_codes_beyond(self, excluded: set[str]) -> set[Glyph]:
        encoding = SimpleEncoding(self.encoding)
        return {Glyph(self.text_layer_name, char) for code in self.drawn_codes - excluded
                if (char := encoding.char_for(code))}

    def emitted_at(self, code: str) -> str | None:
        mapped = next((emitted for mapped_code, _, emitted in self._mapping_rows if mapped_code == code), None)
        return mapped if mapped is not None else self._glyph_name_char(code)

    def _glyph_name_char(self, code: str) -> str | None:
        name = self.glyph_names.get(code)
        return glyph_name_char(name) if name else None

    def glyph_name_names(self, code: str, char: str) -> bool:
        return not is_suspect(char) and self._glyph_name_char(code) == char

    def flagged_codes(self) -> list[tuple[str, str]]:
        return [(code, emitted) for code, target, emitted in self._emission_rows()
                if self._is_flagged_mapping(code, target)]

    def _is_flagged_mapping(self, code: str, target: str) -> bool:
        return _is_suspect_mapping(code, target) or self._contradicts_its_glyph_name(code, target)

    def _contradicts_its_glyph_name(self, code: str, target: str) -> bool:
        named = self._glyph_name_identity(code)
        return named is not None and compatible(named) != compatible(target)

    def _glyph_name_identity(self, code: str) -> str | None:
        name = self.glyph_names.get(code)
        return GlyphName(name).identity() if name else None

    def _emission_rows(self) -> list[tuple[str, str, str]]:
        mapped = {code for code, _, _ in self._mapping_rows}
        named = ((code, self._glyph_name_char(code)) for code in self.glyph_names if code not in mapped)
        return self._mapping_rows + [(code, char, char) for code, char in named if char is not None]

    def _stand_in_codes_for(self, char: str) -> list[str]:
        return [code for code, target, emitted in self._mapping_rows if emitted == char and emitted != target]

    def _mapped_codes_for(self, char: str) -> list[str]:
        return [code for code, target, _ in self._mapping_rows if target == char]

    def _unmapped_codes_for(self, char: str) -> list[str]:
        if self.cid_font is not None:
            return []
        mapped = self.cmap.mappings()
        return [code for code in self._codes_emitted_as(char) if code not in mapped]

    def _codes_emitted_as(self, char: str) -> list[str]:
        code = SimpleEncoding(self.encoding).code_for(char)
        return [] if code is None else [code]

    @cached_property
    def _mapping_rows(self) -> list[tuple[str, str, str]]:
        mappings = self.cmap.mappings() if self.cmap is not None else {}
        return [(code, target, self._emitted(code, target)) for code, target in mappings.items()]

    @cached_property
    def _emitted_characters(self) -> frozenset[str]:
        return frozenset(emitted for _, _, emitted in self._mapping_rows)

    def _emitted(self, code: str, target: str) -> str:
        return self.cid_font.emitted(code, target) if self.cid_font is not None else target


def _is_suspect_mapping(code: str, target: str) -> bool:
    if target == "":
        return True
    return len(target) == 1 and is_suspect(target) and not _is_identity_mapping(code, target)


def _is_identity_mapping(code: str, target: str) -> bool:
    return int(code, HEX_RADIX) == ord(target)


class PdfFonts:
    def __init__(self, pdf_path: Path) -> None:
        self._path = pdf_path

    def records(self) -> list[FontRecord]:
        try:
            return self._read_records()
        except READ_FAILURES as failure:
            raise FontReadError(f"cannot read the fonts of {self._path.name}: {failure}") from failure

    def _read_records(self) -> list[FontRecord]:
        pages_by_xref = self._pages_by_xref()
        ocr_layers = _OcrLayerNames(self._path).names()
        with pikepdf.open(self._path) as pdf:
            records = [_FontDictionary(pdf, xref).record(pages) for xref, pages in sorted(pages_by_xref.items())]
        return [replace(record, ocr_layer=record.text_layer_name in ocr_layers) for record in records]

    def _pages_by_xref(self) -> dict[int, set[int]]:
        pages_by_xref: dict[int, set[int]] = {}
        with pymupdf.open(self._path) as doc:
            for index, page in enumerate(doc):
                for xref in _font_xrefs(page):
                    pages_by_xref.setdefault(xref, set()).add(index)
        return pages_by_xref


class _OcrLayerNames:
    def __init__(self, pdf_path: Path) -> None:
        self._path = pdf_path
        self._invisible: set[str] = set()
        self._visible: set[str] = set()
        self._on_scanned_pages: set[str] = set()
        self._elsewhere: set[str] = set()

    def names(self) -> set[str]:
        with pymupdf.open(self._path) as doc:
            for page in doc:
                self._sort_spans_of(page)
        return (self._invisible - self._visible) | (self._on_scanned_pages - self._elsewhere)

    def _sort_spans_of(self, page: pymupdf.Page) -> None:
        scanned = _is_covered_by_an_image(page)
        for span in page.get_texttrace():
            (self._invisible if span["type"] == INVISIBLE_TEXT_TYPE else self._visible).add(span["font"])
            (self._on_scanned_pages if scanned else self._elsewhere).add(span["font"])


def _is_covered_by_an_image(page: pymupdf.Page) -> bool:
    page_area = page.rect.get_area()
    covered = ((pymupdf.Rect(image["bbox"]) & page.rect).get_area() for image in page.get_image_info())
    return any(area >= FULL_PAGE_IMAGE_COVERAGE * page_area for area in covered)


def _font_xrefs(page: pymupdf.Page) -> set[int]:
    return {font[XREF_FIELD] for font in page.get_fonts() if font[XREF_FIELD] != NO_XREF}


class _FontDictionary:
    def __init__(self, pdf: pikepdf.Pdf, xref: int) -> None:
        self._xref = xref
        self._font = pdf.get_object((xref, FIRST_GENERATION))

    def record(self, pages: set[int]) -> FontRecord:
        cmap = self._cmap()
        status = None if cmap is not None else self._failure_status()
        return FontRecord(self._xref, self._basefont(), frozenset(pages), self._glyph_names(), cmap, status,
                          self._cid_font(), self._encoding_name(), drawn_codes=self._drawn_codes())

    def _drawn_codes(self) -> frozenset[str]:
        widths = self._font.get(WIDTHS_KEY)
        first_code = self._font.get(FIRST_CHAR_KEY)
        if not isinstance(widths, pikepdf.Array) or first_code is None:
            return frozenset()
        return frozenset(hex_code(int(first_code) + offset, ONE_BYTE_HEX_WIDTH)
                         for offset, width in enumerate(widths) if float(width) > 0)

    def _basefont(self) -> str:
        return name_text(self._font.get(BASEFONT_KEY, ""))

    def _encoding_name(self) -> str | None:
        encoding = self._font.get(ENCODING_KEY)
        if isinstance(encoding, pikepdf.Dictionary):
            return name_text(encoding[BASE_ENCODING_KEY]) if BASE_ENCODING_KEY in encoding else None
        return name_text(encoding) if encoding is not None else None

    def _glyph_names(self) -> dict[str, str]:
        encoding = self._font.get(ENCODING_KEY)
        if not isinstance(encoding, pikepdf.Dictionary) or DIFFERENCES_KEY not in encoding:
            return {}
        return parse_differences(list(encoding[DIFFERENCES_KEY]))

    def _cid_font(self) -> CidFont | None:
        descendant = self._descendant()
        if descendant is None:
            return None
        identity_encoded = name_text(self._font.get(ENCODING_KEY, "")) in IDENTITY_ENCODINGS
        return CidFont(name_text(descendant.get(BASEFONT_KEY, "")), identity_encoded)

    def _descendant(self) -> pikepdf.Dictionary | None:
        descendants = self._font.get(DESCENDANT_FONTS_KEY)
        is_type0 = name_text(self._font.get(SUBTYPE_KEY, "")) == TYPE0_SUBTYPE
        if not is_type0 or not isinstance(descendants, pikepdf.Array) or len(descendants) == 0:
            return None
        return descendants[FIRST_DESCENDANT]

    def _cmap(self) -> ToUnicodeCMap | None:
        stream = self._font.get(TOUNICODE_KEY)
        if not isinstance(stream, pikepdf.Stream):
            return None
        try:
            return ToUnicodeCMap.from_bytes(stream.read_bytes())
        except (CMapError, pikepdf.PdfError):
            return None

    def _failure_status(self) -> str:
        if isinstance(self._font.get(TOUNICODE_KEY), pikepdf.Stream):
            return UNPARSABLE_TOUNICODE
        return NO_TOUNICODE
