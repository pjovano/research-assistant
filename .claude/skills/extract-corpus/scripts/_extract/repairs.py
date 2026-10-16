from __future__ import annotations

import json
from pathlib import Path

import pymupdf
from font_repair_record import FONT_REPAIR_RECORD_KEY

RECORD_KEY = FONT_REPAIR_RECORD_KEY
_TRAILER_XREF = -1
_INFO_KEY = "Info"
_KIND_XREF = "xref"
_KIND_STRING = "string"


class FontRepairRecord:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path

    def entries(self) -> list[dict]:
        with pymupdf.open(self._pdf_path) as document:
            return self._parsed(self._raw_record(document))

    def _raw_record(self, document) -> str:
        info = document.xref_get_key(_TRAILER_XREF, _INFO_KEY)
        if info[0] != _KIND_XREF:
            return ""
        kind, value = document.xref_get_key(int(info[1].split()[0]), RECORD_KEY)
        return value if kind == _KIND_STRING else ""

    def _parsed(self, raw: str) -> list[dict]:
        try:
            parsed = json.loads(raw) if raw else []
        except ValueError:
            return []
        return parsed if isinstance(parsed, list) else []
