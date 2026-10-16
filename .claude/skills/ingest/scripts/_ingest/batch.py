from __future__ import annotations

import json
from pathlib import Path

import vault

from _drive.work import BY_KEY_NAME, ROUTED_FIELD, STATE_NAME

STAGE_CLEAN = "clean"
STAGE_FILE = "file"
STAGE_EXTRACT = "extract"
STAGE_CITE = "cite"
STAGE_CLASSIFY = "classify"
STAGE_FOUR_FIELDS = ("source_type", "source_role")


class BatchWorkDirectory:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def state(self) -> dict:
        try:
            return json.loads((self._directory / STATE_NAME).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}


class FiledWork:
    def __init__(self, basename: str) -> None:
        self._basename = basename
        self._meta, self._body = vault.read_frontmatter(vault.held_note_path(basename))

    def stage(self) -> str | None:
        if not vault.body_after_pdf_link(self._body).strip():
            return STAGE_EXTRACT
        if not any(self._meta.get(field) for field in STAGE_FOUR_FIELDS):
            return STAGE_CITE
        return None


class BatchListing:
    def __init__(self, inbox: Path, works_dir: Path) -> None:
        self._inbox = inbox
        self._works_dir = works_dir

    def works(self) -> list[dict]:
        return self._inbox_works() + self._filed_works()

    def _inbox_works(self) -> list[dict]:
        return [{"pdf": vault.nfc(path.name), "from": self._inbox_stage(path)} for path in vault.list_pdfs(self._inbox)]

    def _inbox_stage(self, pdf: Path) -> str:
        state = BatchWorkDirectory(self._works_dir / vault.basename_of(pdf)).state()
        return STAGE_FILE if state.get(ROUTED_FIELD) else STAGE_CLEAN

    def _filed_works(self) -> list[dict]:
        batched = self._batched_basenames()
        staged = [(basename, FiledWork(basename).stage()) for basename in batched]
        staged += [(basename, STAGE_CITE) for basename in self._unclassified_unbatched(set(batched))]
        return [{"basename": basename, "from": stage} for basename, stage in staged if stage is not None]

    def _unclassified_unbatched(self, batched: set[str]) -> list[str]:
        unbatched = [basename for basename in self._corpus_basenames() if basename not in batched]
        return [basename for basename in unbatched if FiledWork(basename).stage() == STAGE_CITE]

    def _batched_basenames(self) -> list[str]:
        directories = sorted(self._works_dir.iterdir()) if self._works_dir.is_dir() else []
        return [vault.nfc(directory.name) for directory in directories
                if directory.is_dir() and directory.name != BY_KEY_NAME and vault.held_note_exists(directory.name)]

    @staticmethod
    def _corpus_basenames() -> list[str]:
        return sorted(vault.nfc(path.stem) for path in vault.list_corpus_files())
