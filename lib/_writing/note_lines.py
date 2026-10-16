from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .atomic_note import TASKS, AtomicNote, ReferencePlace
from .claims import ClaimsBlock, marked_for_review
from .note_check import QUOTATION_RELATIONS
from .quotations import BENEATH_QUOTATION, VerifiedQuotation
from .task_list import TAG_SEPARATOR, THREAD_TAG_RE, THREADS
from .tree import WritingFolders
from .saved import save_text

OPEN_TASK_MARK = "- [ ] "
TASK_BOX_RE = re.compile(r"^(?:- \[[ x]\] )+")


class NoteFile:
    def __init__(self, folders: WritingFolders, title: str) -> None:
        self.title = title
        self._path = folders.atomic_note(title)
        if not self._path.is_file():
            raise ValueError(f"no note named {title!r} in {folders.notes}")

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> AtomicNote:
        return AtomicNote(self._path.read_text(encoding="utf-8"))

    def write(self, note: AtomicNote) -> None:
        save_text(self._path, note.text)


@dataclass(frozen=True)
class ClaimLine:
    number: int
    text: str


class ClaimWording:
    def __init__(self, file: NoteFile, claim: ClaimLine) -> None:
        self._file = file
        self._claim = ClaimLine(claim.number, marked_for_review(self._required(claim.text)))
        self._written = self._claims().with_claim(claim.number, self._claim.text)

    def plan(self) -> dict:
        return {"note": self._file.title, "claim": self._claim.number, "line": self._claim.text}

    def apply(self) -> None:
        self._file.write(self._file.read().with_claims(self._written))

    def _claims(self) -> ClaimsBlock:
        return ClaimsBlock(self._file.read().claims_block)

    @staticmethod
    def _required(text: str) -> str:
        if not text.strip():
            raise ValueError("a claim holds words")
        return text.strip()


class Explication:
    def __init__(self, file: NoteFile, claim: ClaimLine) -> None:
        self._file = file
        self._claim = ClaimLine(claim.number, marked_for_review(self._required(claim.text)))
        self._written = ClaimsBlock(file.read().claims_block).with_explication(claim.number, self._claim.text)

    def plan(self) -> dict:
        return {"note": self._file.title, "beneath_claim": self._claim.number, "line": self._claim.text}

    def apply(self) -> None:
        self._file.write(self._file.read().with_claims(self._written))

    @staticmethod
    def _required(text: str) -> str:
        if not text.strip():
            raise ValueError("an explication holds words")
        return text.strip()


class NoteTask:
    def __init__(self, file: NoteFile, task: str) -> None:
        words = TASK_BOX_RE.sub("", task.strip())
        if not THREAD_TAG_RE.match(words):
            raise ValueError(f"a task opens with its thread's tag, one of {['#' + thread for thread in THREADS]}, "
                             f"then {TAG_SEPARATOR.strip()!r} and its words")
        self._file = file
        self._line = f"{OPEN_TASK_MARK}{words}"

    def plan(self) -> dict:
        return {"note": self._file.title, "line": self._line}

    def apply(self) -> None:
        self._file.write(self._file.read().with_line_last(TASKS, self._line))


@dataclass(frozen=True)
class ReferenceFraming:
    relation: str
    comment: str = ""
    after: int | None = None
    group: str = ""
    before: str = ""


class ReferenceWriting:
    def __init__(self, file: NoteFile, quotation: VerifiedQuotation, framing: ReferenceFraming) -> None:
        if framing.relation not in QUOTATION_RELATIONS:
            raise ValueError(f"a quotation's relation is one of {list(QUOTATION_RELATIONS)}")
        if framing.after is None and not framing.group.strip():
            raise ValueError("a reference stands under a group of the note's references: name it with --group, "
                             "or the reference it follows with --after")
        if framing.before.strip() and framing.after is not None:
            raise ValueError("--before places a new group named with --group: it never goes with --after")
        self._file = file
        self._quotation = quotation
        self._framing = framing
        place = ReferencePlace(framing.group, framing.after, framing.before)
        self._written = file.read().with_reference(self._block(), place)

    def plan(self) -> dict:
        return {"note": self._file.title, "reference": self._block(),
                "notation_to_read_on_the_page": list(self._quotation.notation_to_read)}

    def apply(self) -> None:
        self._file.write(self._written)

    def _block(self) -> str:
        opening = marked_for_review(f"> **{self._framing.relation}** · “{self._quotation.wording}”")
        comment = [f"{BENEATH_QUOTATION}{line.strip()}" for line in self._framing.comment.splitlines() if line.strip()]
        return "\n".join([opening, self._quotation.source_line, *comment])
