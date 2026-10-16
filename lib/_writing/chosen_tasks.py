from __future__ import annotations

import re
from dataclasses import dataclass

from .atomic_note import TASKS, AtomicNote
from .drafts import MARKDOWN_SUFFIX
from .note_lines import ClaimLine, ClaimWording, NoteFile
from .placement import NoteCreation
from .task_list import ACCEPT_TASK_RE, ENRICH, NOTE_THREADS, TAG_SEPARATOR
from .tree import WritingFolders

CHOSEN_MARK = "- [x] "
DONE_DATE = r"(?: ✅ \d{4}-\d{2}-\d{2})?"
NOTE_THREAD_TAG = rf"#(?P<thread>{'|'.join(NOTE_THREADS)}){TAG_SEPARATOR}"
CHOSEN_TASK_RE = re.compile(
    rf"^- \[x\] {NOTE_THREAD_TAG}Take notes on “(?P<title>[^”]+)”: (?P<claim>.+?)(?:; from .*?)?{DONE_DATE}$")
RETAGGED_TASK_RE = re.compile(rf"^- \[x\] {NOTE_THREAD_TAG}(?P<words>.+?){DONE_DATE}$")
ENRICH_TASK_RE = re.compile(rf"^- \[x\] #{ENRICH}{TAG_SEPARATOR}(?P<words>.+?){DONE_DATE}$")
RESEARCH = "research"
REVIEW = "review"


@dataclass(frozen=True)
class ChosenTask:
    reviewed: str
    thread: str
    title: str
    claim: str
    line: str

    def as_json(self, state: str) -> dict:
        return {"reviewed": self.reviewed, "thread": self.thread, "title": self.title, "line": self.line, "state": state}


class ChosenTasks:
    def __init__(self, folders: WritingFolders, limit: int) -> None:
        self._folders = folders
        self._tasks: list[ChosenTask] = []
        self._unparsed: list[dict] = []
        self._retagged: list[dict] = []
        self._researched: dict[str, bool] = {}
        self._read()
        self._refused = self._refusals()
        keys = list(dict.fromkeys(self._key(task) for task in self._tasks if task.title not in self._refused))
        self._taken = set(keys[:limit])
        stubs = self._stubs()
        self._stubs_taken = stubs[:max(0, limit - len(self._taken))]
        self._stubs_deferred = stubs[len(self._stubs_taken):]

    def plan(self) -> dict:
        return {"tasks": [task.as_json(self._state_of(task)) for task in self._tasks if self._key(task) in self._taken],
                "deferred": [task.as_json(self._state_of(task)) for task in self._tasks if self._deferred(task)],
                "to_create": self._to_create(),
                "refused": [{"title": title, "reason": reason} for title, reason in self._refused.items()],
                "retagged": self._retagged,
                "unparsed": self._unparsed,
                "stubs": self._stubs_taken,
                "deferred_stubs": self._stubs_deferred}

    def apply(self) -> None:
        for title in self._to_create():
            NoteCreation(self._folders, title).apply()
            first = next(task for task in self._tasks if task.title == title)
            ClaimWording(NoteFile(self._folders, title), ClaimLine(1, first.claim)).apply()

    def _read(self) -> None:
        for path in sorted(self._folders.notes.glob(f"*{MARKDOWN_SUFFIX}")) if self._folders.notes.is_dir() else []:
            note = AtomicNote(path.read_text(encoding="utf-8"))
            self._researched[path.stem] = self._is_researched(note)
            for line in note.lines(TASKS).splitlines():
                self._take(path.stem, line.strip())

    @staticmethod
    def _is_researched(note: AtomicNote) -> bool:
        claims = note.claims()
        return bool(note.reference_blocks()) or not claims or not all(claims)

    def _stubs(self) -> list[str]:
        further = {task.title for task in self._tasks if task.thread != ENRICH}
        return [title for title, researched in self._researched.items() if not researched and title not in further]

    def _take(self, reviewed: str, line: str) -> None:
        if not line.startswith(CHOSEN_MARK) or ACCEPT_TASK_RE.match(line):
            return
        enriching = ENRICH_TASK_RE.match(line)
        if enriching is not None:
            self._tasks.append(ChosenTask(reviewed, ENRICH, reviewed, enriching.group("words").strip(), line))
            return
        hit = CHOSEN_TASK_RE.match(line)
        if hit is None:
            self._set_aside(reviewed, line)
            return
        self._tasks.append(ChosenTask(reviewed, hit.group("thread"), hit.group("title").strip(), hit.group("claim").strip(), line))

    def _set_aside(self, reviewed: str, line: str) -> None:
        retagged = RETAGGED_TASK_RE.match(line)
        if retagged is None:
            self._unparsed.append({"reviewed": reviewed, "line": line})
            return
        self._retagged.append({"reviewed": reviewed, "thread": retagged.group("thread"), "line": line})

    def _refusals(self) -> dict[str, str]:
        refused = {}
        for title in dict.fromkeys(task.title for task in self._tasks if task.thread != ENRICH and not self._held(task.title)):
            try:
                NoteCreation(self._folders, title)
            except ValueError as refusal:
                refused[title] = str(refusal)
        return refused

    def _to_create(self) -> list[str]:
        return [title for title in dict.fromkeys(task.title for task in self._tasks if task.thread != ENRICH)
                if title in self._taken and not self._held(title)]

    def _deferred(self, task: ChosenTask) -> bool:
        return self._key(task) not in self._taken and task.title not in self._refused

    @staticmethod
    def _key(task: ChosenTask) -> str:
        return task.line if task.thread == ENRICH else task.title

    def _state_of(self, task: ChosenTask) -> str:
        return ENRICH if task.thread == ENRICH else self._state(task.title)

    def _state(self, title: str) -> str:
        if not self._held(title):
            return RESEARCH
        note = AtomicNote(self._folders.atomic_note(title).read_text(encoding="utf-8"))
        return REVIEW if note.reference_blocks() else RESEARCH

    def _held(self, title: str) -> bool:
        return self._folders.atomic_note(title).is_file()
