from __future__ import annotations

from pathlib import Path

import pymupdf
import vault

TRIM_DPI = 300
TRIMMED_SUFFIX = ".trimmed.png"
DEFAULT_PAPER = "a4"


class CoverImage:
    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def require_exists(self) -> "CoverImage":
        if not self._path.exists():
            raise SystemExit(f"Cover image not found: {self._path}")
        return self

    def trimmed(self, top: float, bottom: float) -> "CoverImage":
        if not top and not bottom:
            return self
        destination = self._trim_destination()
        self._save_trim(destination, top, bottom)
        return CoverImage(destination)

    def width_for(self, height: float) -> float:
        with pymupdf.open(self._path) as img:
            aspect = img[0].rect.width / img[0].rect.height
        return height * aspect

    def _trim_destination(self) -> Path:
        return vault.SCRATCH_DIR / f"{self._path.stem}{TRIMMED_SUFFIX}"

    def _save_trim(self, destination: Path, top: float, bottom: float) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(self._path) as img:
            clip = self._cropped_rect(img[0].rect, top, bottom)
            img[0].get_pixmap(clip=clip, dpi=TRIM_DPI).save(destination)

    def _cropped_rect(self, rect: pymupdf.Rect, top: float, bottom: float) -> pymupdf.Rect:
        clip = pymupdf.Rect(
            rect.x0, rect.y0 + rect.height * top, rect.x1, rect.y1 - rect.height * bottom,
        )
        if clip.height <= 0:
            raise SystemExit("Crop removes the whole image; check --crop-top/--crop-bottom.")
        return clip


class CoverPage:
    def __init__(self, doc: pymupdf.Document) -> None:
        self._doc = doc

    def prepend(self, image: CoverImage) -> None:
        height = self._body_rect().height
        page = self._doc.new_page(pno=0, width=image.width_for(height), height=height)
        page.insert_image(page.rect, filename=str(image.path), keep_proportion=True)

    def _body_rect(self) -> pymupdf.Rect:
        return self._doc[0].rect if self._doc.page_count else pymupdf.paper_rect(DEFAULT_PAPER)
