from __future__ import annotations

import json
from pathlib import Path

import vault

from _extract.correctionanchors import CorrectionContext
from _extract.correctionrun import CorrectionPass, PassResult, parsed_corrections
from _extract.correctiontext import TrialText, normalized
from _extract.layer import TextLayer
from _extract.outline import Outline
from _extract.paths import CorpusFile
from _extract.trial import TRIALS_DIR_NAME

CORRECTIONS_SUFFIX = ".corrections.json"
_ENCODING = "utf-8"


class TrialCorrections:
    def __init__(self, note: CorpusFile) -> None:
        self._path = vault.SCRATCH_DIR / TRIALS_DIR_NAME / f"{note.basename}{CORRECTIONS_SUFFIX}"

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> list[dict]:
        if not self._path.is_file():
            return []
        return json.loads(self._path.read_text(encoding=_ENCODING))

    def save(self, corrections: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(corrections, indent=2, ensure_ascii=False) + "\n", encoding=_ENCODING)

    def discard(self) -> None:
        self._path.unlink(missing_ok=True)


class LayerLines:
    def __init__(self, layer: TextLayer) -> None:
        self._layer = layer

    def lines(self, file_page: int) -> list[str]:
        return [line.text for line in self._layer.lines(file_page)]

    def is_drawn(self, file_page: int) -> bool:
        return self._layer.has_text(file_page) and self._layer.is_drawn(file_page)


class WorkContext:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path

    def corrected(self, body: str, corrections: object) -> PassResult:
        titles = frozenset(normalized(heading.title).casefold() for heading in Outline(self._pdf_path).headings())
        context = CorrectionContext(TrialText.parsed(body), titles, LayerLines(TextLayer(self._pdf_path)))
        return CorrectionPass(context).run(TrialText.parsed(body), parsed_corrections(corrections))
