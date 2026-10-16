from __future__ import annotations

from pathlib import Path

import pikepdf
import vault

QPDF_SUFFIX = ".qpdf.pdf"


class QpdfRepair:
    def __init__(self, src_path: Path) -> None:
        self._src = src_path
        self._dest = vault.SCRATCH_DIR / f"{src_path.stem}{QPDF_SUFFIX}"

    @property
    def destination(self) -> Path:
        return self._dest

    def run(self) -> None:
        self._dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._rewrite()
        except pikepdf.PdfError as error:
            self._dest.unlink(missing_ok=True)
            raise SystemExit(f"qpdf could not repair {self._src.name}: {error}") from error

    def _rewrite(self) -> None:
        with pikepdf.open(self._src) as pdf:
            pdf.save(self._dest, stream_decode_level=pikepdf.StreamDecodeLevel.none)
