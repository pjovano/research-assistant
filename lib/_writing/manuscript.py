from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

import zotero

from .citations import DraftCitations
from .conversion import ExportText, StyledDocx
from .docx_style import DocxStyle
from .pandoc import Pandoc

DOCX, PDF = "docx", "pdf"
KINDS = (DOCX, PDF)
CSL_SUFFIX = ".csl"
STYLES_DIRECTORY = Path.home() / "Zotero" / "styles"


@dataclass(frozen=True)
class ManuscriptFormat:
    kind: str
    style: DocxStyle
    csl: str | None = None


class CslStyle:
    def __init__(self, name: str | None, directory: Path = STYLES_DIRECTORY) -> None:
        self._name = name
        self._directory = directory

    def options(self) -> list[str]:
        if self._name is None:
            return []
        path = self._directory / f"{self._name}{CSL_SUFFIX}"
        if not path.is_file():
            raise ValueError(f"no citation style named {self._name!r} in {self._directory}: it holds {self._held()}")
        return ["--csl", str(path)]

    def _held(self) -> list[str]:
        return sorted(path.stem for path in self._directory.glob(f"*{CSL_SUFFIX}")) if self._directory.is_dir() else []


class ZoteroRecords:
    def of(self, keys: list[str]) -> list[dict]:
        if not zotero.is_online():
            raise ValueError("Zotero is not running: a draft that cites needs it for its bibliography")
        records = {key: zotero.get_csl_record(key) for key in keys}
        missing = [key for key, record in records.items() if record is None]
        if missing:
            raise ValueError(f"Zotero holds no record under {missing}: correct each citekey in the draft")
        return [{**record, "id": key} for key, record in records.items()]


class ManuscriptExport:
    def __init__(self, note: Path, directory: Path, manuscript: ManuscriptFormat) -> None:
        self._note = note
        self._format = manuscript
        self._target = directory / f"{note.stem}.{manuscript.kind}"
        self._markdown = ExportText(note.read_text(encoding="utf-8")).markdown()
        self._keys = DraftCitations(self._markdown).keys()
        self._csl = CslStyle(manuscript.csl).options()
        if self._target.exists():
            raise ValueError(f"{self._target} exists: name another directory")

    def plan(self) -> dict:
        return {"note": str(self._note), self._format.kind: str(self._target), "style": self._format.style.name,
                "citekeys": self._keys, "citation_style": self._format.csl or "pandoc's default, Chicago author-date"}

    def apply(self, records: ZoteroRecords | None = None, pandoc: Pandoc | None = None) -> None:
        pandoc = pandoc or Pandoc()
        self._target.parent.mkdir(parents=True, exist_ok=True)
        if self._format.kind == DOCX and not self._keys:
            StyledDocx(self._format.style, pandoc).write(self._markdown, self._target)
            return
        with tempfile.TemporaryDirectory() as scratch:
            options = [*self._citing(Path(scratch), records or ZoteroRecords()), *self._typesetting(Path(scratch), pandoc)]
            pandoc.write_manuscript(self._markdown, self._target, options)

    def _citing(self, scratch: Path, records: ZoteroRecords) -> list[str]:
        if not self._keys:
            return []
        bibliography = scratch / "bibliography.json"
        bibliography.write_text(json.dumps(records.of(self._keys), ensure_ascii=False), encoding="utf-8")
        return ["--citeproc", "--bibliography", str(bibliography), *self._csl]

    def _typesetting(self, scratch: Path, pandoc: Pandoc) -> list[str]:
        style = self._format.style
        if self._format.kind == PDF:
            return ["--pdf-engine=typst", "-V", f"mainfont={style.font}", "-V", f"fontsize={style.body_points}pt"]
        return ["--reference-doc", str(StyledDocx(style, pandoc).reference_in(scratch))]
