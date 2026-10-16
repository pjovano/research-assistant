from __future__ import annotations

import html
import io
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from PIL import Image
from pylatexenc.latex2text import LatexNodes2Text
from pylatexenc.latexwalker import LatexWalkerError

from engine_guard import EngineUnresponsive, GuardedEngineModels, PendingGeneration
from engine_slots import SlotsAgreement
from latex_symbols import with_supplementary_unicode
from surya_servers import EngineRun

from .lines import TextLine
from .render import widened

CROP_DPI = 200
CROP_MARGIN_X = 20.0
CROP_MARGIN_Y = 12.0
OCR_BATCH_SIZE = 64
PIXMAP_FORMAT = "png"
IMAGE_MODE = "RGB"
_MATH_RE = re.compile(r"<math[^>]*>(.*?)</math>", re.DOTALL)
_TAG_RE = re.compile(r"</?[A-Za-z][^<>]*>")
INFERENCE_MANAGER = "inference_manager"
LINES_PER_SHEET = 8
SHEET_GAP = 12
SHEET_PADDING = 20
SHEET_BACKGROUND = "white"
SHEET_LINE_JOIN = " "
JOIN_GLYPH_FONT = ""
TOKENS_PER_CHARACTER = 2
TOKEN_CAP_MARGIN = 100
VISION_LEVEL = "accurate"
VISION_LANGUAGES = ["en-US", "de-DE", "fr-FR", "it-IT", "es-ES"]
VISION_TEXT_FIELD = 0
VISION_BOX_FIELD = 2
VISION_LEFT = 0
VISION_LIMIT_SECONDS = 120.0


class LineCrops:
    def __init__(self, pdf_path: Path, dpi: int = CROP_DPI) -> None:
        self._path = pdf_path
        self._dpi = dpi

    def images(self, lines: list[TextLine]) -> list[Image.Image]:
        with pymupdf.open(self._path) as doc:
            return [self._image(doc[line.page], line) for line in lines]

    def _image(self, page: pymupdf.Page, line: TextLine) -> Image.Image:
        clip = widened(pymupdf.Rect(*line.bbox), CROP_MARGIN_X, CROP_MARGIN_Y) & page.rect
        pixmap = page.get_pixmap(dpi=self._dpi, clip=clip)
        return Image.open(io.BytesIO(pixmap.tobytes(PIXMAP_FORMAT))).convert(IMAGE_MODE)


class OcrText:
    def __init__(self) -> None:
        self._latex = LatexNodes2Text()

    def plain(self, html_text: str) -> str:
        with_unicode_math = _MATH_RE.sub(lambda match: self._unicode_math(html.unescape(match.group(1))), html_text)
        return html.unescape(_TAG_RE.sub("", with_unicode_math))

    def _unicode_math(self, latex: str) -> str:
        supplemented = with_supplementary_unicode(latex)
        try:
            return self._latex.latex_to_text(supplemented)
        except (LatexWalkerError, ValueError):
            return supplemented


class VisionUnresponsive(RuntimeError):
    def __init__(self, limit_seconds: float) -> None:
        super().__init__(f"Apple Vision returned no reading of a line within {limit_seconds:.0f} seconds; the pixel "
                         f"check stopped and cached nothing, so the next run reads every line again")


class VisionUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Apple Vision is not available on this machine: the pixel check reads plain glyphs through "
                         "ocrmac, which runs only on macOS; run the command on a Mac")


class VisionRecognizer:
    def found(self, image: Image.Image) -> list:
        try:
            from ocrmac import ocrmac
        except ImportError as missing:
            raise VisionUnavailable() from missing
        return ocrmac.OCR(image, recognition_level=VISION_LEVEL, language_preference=VISION_LANGUAGES).recognize()


class VisionReader:
    def __init__(self, pdf_path: Path, recognizer: VisionRecognizer | None = None,
                 limit_seconds: float = VISION_LIMIT_SECONDS) -> None:
        self._path = pdf_path
        self._recognizer = recognizer or VisionRecognizer()
        self._limit_seconds = limit_seconds

    def read(self, lines: list[TextLine]) -> list[tuple[TextLine, str | None]]:
        return list(zip(lines, (self._read_one(image) for image in LineCrops(self._path).images(lines))))

    def _read_one(self, image: Image.Image) -> str | None:
        ordered = sorted(self._found_within_the_limit(image), key=lambda entry: entry[VISION_BOX_FIELD][VISION_LEFT])
        text = " ".join(entry[VISION_TEXT_FIELD] for entry in ordered).strip()
        return text or None

    def _found_within_the_limit(self, image: Image.Image) -> list:
        pending = PendingGeneration(lambda: self._recognizer.found(image))
        if not pending.finished_within(self._limit_seconds):
            raise VisionUnresponsive(self._limit_seconds)
        return pending.outcome()


class LineSheet:
    def __init__(self, lines: list[TextLine], images: list[Image.Image]) -> None:
        self._lines = lines
        self._images = images

    def merged_line(self) -> TextLine:
        text = SHEET_LINE_JOIN.join(line.text for line in self._lines)
        fonts_with_joins = tuple(font for line in self._lines for font in line.fonts + (JOIN_GLYPH_FONT,))
        fonts = fonts_with_joins[:-1]
        return TextLine(self._lines[0].page, self._lines[0].bbox, text, fonts)

    def image(self) -> Image.Image:
        width = max(image.width for image in self._images) + 2 * SHEET_PADDING
        height = sum(image.height for image in self._images) + SHEET_GAP * (len(self._images) - 1) + 2 * SHEET_PADDING
        sheet = Image.new(IMAGE_MODE, (width, height), SHEET_BACKGROUND)
        top = SHEET_PADDING
        for image in self._images:
            sheet.paste(image, (SHEET_PADDING, top))
            top += image.height + SHEET_GAP
        return sheet

    def token_cap(self) -> int:
        return len(self.merged_line().text) * TOKENS_PER_CHARACTER + TOKEN_CAP_MARGIN


@dataclass(frozen=True)
class EngineReadings:
    readings: list[tuple[TextLine, str | None]]
    unread_sheets: int

    @staticmethod
    def none() -> "EngineReadings":
        return EngineReadings([], 0)


class EngineReader:
    def __init__(self, pdf_path: Path, models: dict | None = None, run: EngineRun | None = None) -> None:
        self._path = pdf_path
        self._models = models
        self._run = run or EngineRun(servers_agreement=SlotsAgreement.on_this_machine())
        self._text = OcrText()

    def read(self, lines: list[TextLine]) -> EngineReadings:
        sheets = self._sheets(lines)
        answers = self._generated(sheets)
        readings = [(sheet.merged_line(), self._plain(raw)) for sheet, raw in zip(sheets, answers)]
        return EngineReadings(readings, answers.count(None))

    def _sheets(self, lines: list[TextLine]) -> list[LineSheet]:
        images = LineCrops(self._path).images(lines)
        size = LINES_PER_SHEET
        starts = range(0, len(lines), size)
        return [LineSheet(lines[start:start + size], images[start:start + size]) for start in starts]

    def _generated(self, sheets: list[LineSheet]) -> list[str | None]:
        manager = self._manager()
        from surya.inference.schema import PROMPT_TYPE_BLOCK, BatchInputItem
        batch = [BatchInputItem(image=sheet.image(), prompt_type=PROMPT_TYPE_BLOCK, max_tokens=sheet.token_cap())
                 for sheet in sheets]
        try:
            return [self._raw_or_none(result) for result in self._generated_under_a_recorded_run(manager, batch)]
        except EngineUnresponsive as failure:
            return self._unread(batch, failure)

    @staticmethod
    def _unread(batch: list, failure: EngineUnresponsive) -> list[None]:
        print(f"surya could not read {len(batch)} line sheets: {failure}", file=sys.stderr)
        return [None] * len(batch)

    def _generated_under_a_recorded_run(self, manager, batch: list) -> list:
        self._run.started()
        try:
            return manager.generate(batch)
        finally:
            self._run.finished()

    @staticmethod
    def _raw_or_none(result) -> str | None:
        if result.error:
            print(f"surya could not read a line sheet: {result.error}", file=sys.stderr)
            return None
        return result.raw or ""

    def _plain(self, raw: str | None) -> str | None:
        if raw is None:
            return None
        text = self._text.plain(raw).strip()
        return text or None

    def _manager(self):
        if self._models is None:
            self._models = self._loaded_models()
        return self._models[INFERENCE_MANAGER]

    @staticmethod
    def _loaded_models() -> dict:
        return GuardedEngineModels().created()
