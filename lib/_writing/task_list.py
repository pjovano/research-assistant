from __future__ import annotations

import re

from .atomic_note import TASKS, AtomicNote

OPEN_TASK_BOX = "- [ ] "
ACCEPT = "accept"
ENRICH = "enrich"
NOTE_THREADS = ("focus", "conceptual", "genealogical", "contrary")
THREADS = (*NOTE_THREADS, ENRICH)
TAG_SEPARATOR = " · "
ACCEPT_TASK = f"{OPEN_TASK_BOX}#{ACCEPT}{TAG_SEPARATOR}Accept every line of this note marked for review"
ACCEPT_TASK_RE = re.compile(rf"^- \[[ x]\] #{ACCEPT}{TAG_SEPARATOR}")
CHECKED_ACCEPT_TASK_RE = re.compile(rf"^- \[x\] #{ACCEPT}{TAG_SEPARATOR}")
THREAD_TAG_RE = re.compile(rf"^#(?:{'|'.join(THREADS)}){TAG_SEPARATOR}\S")
TASK_LINE_RE = re.compile(rf"^- \[[ x]\] #(?:{'|'.join((*THREADS, ACCEPT))}){TAG_SEPARATOR}\S")


class TaskList:
    def __init__(self, note: AtomicNote) -> None:
        self._note = note
        self._lines = [line for line in note.lines(TASKS).splitlines() if line.strip()]

    def opens_with_accept_task(self) -> bool:
        return bool(self._lines) and self._lines[0] == ACCEPT_TASK

    def accept_task_checked(self) -> bool:
        return any(CHECKED_ACCEPT_TASK_RE.match(line) for line in self._lines)

    def open_tasks(self) -> int:
        return sum(1 for line in self._other_tasks() if line.startswith(OPEN_TASK_BOX))

    def untagged(self) -> list[str]:
        return [line for line in self._lines if not TASK_LINE_RE.match(line)]

    def with_accept_task_first(self) -> AtomicNote:
        return self._note.with_lines(TASKS, "\n".join([ACCEPT_TASK, *self._other_tasks()]))

    def accepted(self) -> AtomicNote:
        return TaskList(self._note.with_review_marks_accepted()).with_accept_task_first()

    def _other_tasks(self) -> list[str]:
        return [line for line in self._lines if not ACCEPT_TASK_RE.match(line)]
