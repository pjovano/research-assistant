from __future__ import annotations

from .drafts import MARKDOWN_SUFFIX
from .note_lines import NoteFile
from .task_list import TaskList
from .tree import WritingFolders


class NoteAcceptance:
    def __init__(self, folders: WritingFolders) -> None:
        paths = sorted(folders.notes.glob(f"*{MARKDOWN_SUFFIX}")) if folders.notes.is_dir() else []
        self._files = [NoteFile(folders, path.stem) for path in paths]

    def plan(self) -> dict:
        return {"accepted": [{"note": file.title, "lines": file.read().review_marks()} for file in self._accepted()],
                "accept_task_written": [file.title for file in self._lacking_the_task()]}

    def apply(self) -> None:
        for file in self._accepted():
            file.write(TaskList(file.read()).accepted())
        for file in self._lacking_the_task():
            file.write(TaskList(file.read()).with_accept_task_first())

    def _accepted(self) -> list[NoteFile]:
        return [file for file in self._files if TaskList(file.read()).accept_task_checked()]

    def _lacking_the_task(self) -> list[NoteFile]:
        return [file for file in self._files if self._lacks_the_task(TaskList(file.read()))]

    @staticmethod
    def _lacks_the_task(tasks: TaskList) -> bool:
        return not tasks.accept_task_checked() and not tasks.opens_with_accept_task()
