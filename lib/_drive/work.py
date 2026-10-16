from __future__ import annotations

import copy
import json
import os
from pathlib import Path

from _vault.naming import basename_of, nfc

QUEUE_NAME = "queue.txt"
STATE_NAME = "state.json"
WORKS_NAME = "works"
BY_KEY_NAME = "by-key"
WORK_FILE_NAME = "work.json"
INGEST_NAME = "ingest"
PDF_SUFFIX = ".pdf"
STATE_ASIDE = "aside"
STATE_HALT = "halt"
STATE_UNWRITTEN = "unwritten"
ROUTED_FIELD = "routed"
INBOX_PDF_FIELD = "inbox_pdf"
CLASSIFY_ANSWERS_NAME = "classify-answers.json"


class WorkStops(Exception):
    def __init__(self, state: str, **fields) -> None:
        super().__init__(state)
        self.fields = {"state": state, **fields}


class SetAside(WorkStops):
    def __init__(self, question: str) -> None:
        super().__init__(STATE_ASIDE, question=question)


class Halt(WorkStops):
    def __init__(self, question: str) -> None:
        super().__init__(STATE_HALT, question=question)


class Unwritten(WorkStops):
    def __init__(self, question: str) -> None:
        super().__init__(STATE_UNWRITTEN, question=question)


def is_work_key(given: int | str) -> bool:
    return isinstance(given, int) or given.isdigit()


class WorkDirectory:
    def __init__(self, pdf: str, directory: Path, initial_state: dict) -> None:
        self.pdf = pdf
        self.directory = directory
        self._initial_state = initial_state
        directory.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> Path:
        return self.directory / name

    def has(self, name: str) -> bool:
        return self.path(name).exists()

    def load(self, name: str):
        return json.loads(self.path(name).read_text())

    def save(self, name: str, data) -> None:
        self.path(name).write_text(json.dumps(data, ensure_ascii=False, indent=1))

    def write_text(self, name: str, text: str) -> None:
        self.path(name).write_text(text)

    def state(self) -> dict:
        return self.load(STATE_NAME) if self.has(STATE_NAME) else copy.deepcopy(self._initial_state)

    def save_state(self, state: dict) -> None:
        self.save(STATE_NAME, state)

    def matching(self, pattern: str) -> list[Path]:
        return sorted(self.directory.glob(pattern))

    def discard(self, pattern: str) -> None:
        for path in self.matching(pattern):
            path.unlink()

    def outcome(self, fields: dict) -> dict:
        return {"pdf": self.pdf, "dir": str(self.directory), **fields}


class KeyedLinks:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def path(self, key: int) -> Path:
        return self._directory / BY_KEY_NAME / str(key)

    def point(self, key: int, basename: str) -> Path:
        (self._directory / basename).mkdir(parents=True, exist_ok=True)
        link = self.path(key)
        link.parent.mkdir(parents=True, exist_ok=True)
        link.unlink(missing_ok=True)
        link.symlink_to(Path(os.pardir) / basename)
        return link

    def basename(self, key: int) -> str:
        link = self.path(key)
        if not link.is_symlink():
            raise SetAside(f"no work is listed under the key {key}: run ingest.py drive-batch")
        return nfc(Path(os.readlink(link)).name)


class ListedWorks:
    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._links = KeyedLinks(directory)

    @property
    def by_key(self) -> Path:
        return self._directory / BY_KEY_NAME

    def list(self, key: int, pdf: str) -> None:
        basename = basename_of(Path(pdf))
        link = self._links.point(key, basename)
        work_file = {"pdf": pdf, "basename": basename}
        (link / WORK_FILE_NAME).write_text(json.dumps(work_file, ensure_ascii=False), encoding="utf-8")

    def pdf(self, key: int) -> str:
        return self._links.basename(key) + PDF_SUFFIX

    def directory(self, key: int) -> Path:
        self._links.basename(key)
        return self._links.path(key)


class IngestWorks:
    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self.listed = ListedWorks(directory)

    def work(self, key: str) -> WorkDirectory:
        if is_work_key(key):
            return WorkDirectory(self.listed.pdf(int(key)), self.listed.directory(int(key)), {})
        return WorkDirectory(key, self._directory / nfc(key.removesuffix(PDF_SUFFIX)), {})

    def fresh_classify_answers(self, key: str) -> Path:
        work = self.work(key)
        work.discard(CLASSIFY_ANSWERS_NAME)
        return work.path(CLASSIFY_ANSWERS_NAME)


class BackfillQueue:
    def __init__(self, directory: Path, initial_state: dict) -> None:
        self._directory = directory
        self._initial_state = initial_state
        self._listed = ListedWorks(directory.parent / INGEST_NAME)
        self._links = KeyedLinks(directory / WORKS_NAME)

    @property
    def path(self) -> Path:
        return self._directory / QUEUE_NAME

    def write(self, pdfs: list[str]) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        self.path.write_text("".join(f"{pdf}\n" for pdf in pdfs))

    def work(self, key: int | str) -> WorkDirectory:
        if is_work_key(key):
            return self._listed_work(int(key))
        pdf = self._named(key)
        return WorkDirectory(pdf, self._directory / WORKS_NAME / basename_of(Path(pdf)), self._initial_state)

    def _listed_work(self, key: int) -> WorkDirectory:
        pdf = self._listed.pdf(key)
        return WorkDirectory(pdf, self._links.point(key, basename_of(Path(pdf))), self._initial_state)

    @staticmethod
    def _named(basename: str) -> str:
        name = nfc(basename.strip())
        return name if name.endswith(PDF_SUFFIX) else name + PDF_SUFFIX
