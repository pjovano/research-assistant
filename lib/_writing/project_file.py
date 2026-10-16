from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from vault import WIKILINK_RE

from .linked_note import CHILDREN, FIELD, PARENTS, LinkedNote

INITIAL_STATUS = "planning"
STATUSES = ("planning", "drafting", "revising", "submitted", "published")
STATUS = "status"

QUESTION = "Research question"
PROJECT = "Project"
ABSTRACT = "Abstract"
READING_LIST = "Reading list"
DRAFTS = "Drafts"
OPEN_QUESTIONS = "Open questions"
CHANGE_LOG = "Change log"
FEEDBACK = "Feedback"
IN_PROJECT = (ABSTRACT, READING_LIST, DRAFTS, OPEN_QUESTIONS, CHANGE_LOG)
HEADINGS = (QUESTION, PROJECT, *IN_PROJECT, FEEDBACK)
KEPT_HEADINGS = (QUESTION, ABSTRACT, DRAFTS, OPEN_QUESTIONS, CHANGE_LOG, FEEDBACK)
LINE_HEADINGS = (DRAFTS, FEEDBACK)
OPTIONAL_HEADINGS = (OPEN_QUESTIONS, FEEDBACK)
READING_LIST_SUFFIX = " - Reading list"
QUERY_RE = re.compile(r"^```(?:tasks|base)\n.*?^```$", re.MULTILINE | re.DOTALL)
DATA_START_RE = re.compile(r"^(?:# Excalidraw Data|%%\n## Drawing|## Drawing)$", re.MULTILINE)
HEADINGS_BY_NAME = {heading.lower().replace(" ", "-"): heading for heading in LINE_HEADINGS}
LINE_BREAK = "\n"
BLOCK_BREAK = "\n\n"
ADDED, REMOVED, DRAFTED = "added", "removed", "drafted"


@dataclass(frozen=True)
class Change:
    kind: str
    what: str

    @classmethod
    def of_note(cls, kind: str, title: str) -> "Change":
        return cls(kind, f"[[{title}]]")

    def line(self, day: date) -> str:
        return f"- {day.isoformat()} · {self.kind} {self.what}"


def embed(target: str) -> str:
    return f"![[{target}]]"


def joined(first: str, second: str, separator: str) -> str:
    return separator.join(part for part in (first, second) if part)


def top_heading(heading: str) -> str:
    return f"# {heading}"


def top_heading_pattern(heading: str) -> re.Pattern:
    return re.compile(rf"(^{re.escape(top_heading(heading))}\n)(.*?)(?=^# |\Z)", re.MULTILINE | re.DOTALL)


def level_of(heading: str) -> int:
    return 2 if heading in IN_PROJECT else 1


def heading_line(heading: str) -> str:
    return f"{'#' * level_of(heading)} {heading}"


def section_pattern(heading: str) -> re.Pattern:
    marks = "#{1,2}" if heading in IN_PROJECT else "#"
    return re.compile(rf"(^{marks} {re.escape(heading)}\n)(.*?)(?=^{marks} |\Z)", re.MULTILINE | re.DOTALL)


class MarkdownSide:
    def __init__(self, project: str, bodies: dict[str, str]) -> None:
        self._bodies = {**bodies, READING_LIST: f"[[{project}{READING_LIST_SUFFIX}]]"}

    @property
    def text(self) -> str:
        shown = [heading for heading in HEADINGS if heading not in OPTIONAL_HEADINGS or self._bodies.get(heading)]
        sections = [joined(heading_line(heading), self._bodies.get(heading, ""), BLOCK_BREAK) for heading in shown]
        return BLOCK_BREAK.join(sections) + LINE_BREAK


class ProjectFile:
    def __init__(self, text: str) -> None:
        self._note = LinkedNote.parsed(text)

    @classmethod
    def blank(cls, project: str) -> "ProjectFile":
        meta = {STATUS: INITIAL_STATUS, PARENTS: [], CHILDREN: []}
        return cls(LinkedNote(meta, MarkdownSide(project, {}).text).text)

    def with_defaults(self) -> "ProjectFile":
        defaults = {STATUS: INITIAL_STATUS, PARENTS: [], CHILDREN: []}
        missing = {key: value for key, value in defaults.items() if key not in self._note.meta}
        return ProjectFile(LinkedNote({**self._note.meta, **missing}, self._note.body).text)

    def markdown_side(self, project: str) -> str:
        return MarkdownSide(project, {heading: self.body(heading) for heading in KEPT_HEADINGS}).text

    def kept_headings(self) -> list[str]:
        return [heading for heading in KEPT_HEADINGS if heading not in OPTIONAL_HEADINGS or self.body(heading)]

    @property
    def text(self) -> str:
        return self._note.text

    @property
    def status(self) -> str | None:
        return self._note.meta.get(STATUS)

    @property
    def parents(self) -> list[str]:
        return self._note.links(PARENTS)

    @property
    def children(self) -> list[str]:
        return self._note.links(CHILDREN)

    @property
    def bibliographies(self) -> list[str]:
        return self._note.links(FIELD)

    def headings(self) -> list[str]:
        return [heading for heading in HEADINGS if section_pattern(heading).search(self._note.body)]

    def body(self, heading: str) -> str:
        hit = section_pattern(heading).search(self._note.body)
        return QUERY_RE.sub("", hit.group(2)).strip() if hit else ""

    def linked(self, heading: str) -> list[str]:
        return [hit.group("target").strip() for hit in WIKILINK_RE.finditer(self.body(heading))]

    def with_status(self, status: str) -> "ProjectFile":
        return ProjectFile(self._note.with_meta(STATUS, status).text)

    def with_parent(self, name: str) -> "ProjectFile":
        return ProjectFile(self._note.with_link(PARENTS, name).text)

    def with_child(self, name: str) -> "ProjectFile":
        return ProjectFile(self._note.with_link(CHILDREN, name).text)

    def with_changes(self, changes: list[Change], day: date | None = None) -> "ProjectFile":
        logged = self
        for change in changes:
            logged = logged.with_line_last(CHANGE_LOG, change.line(day or date.today()))
        return logged

    def with_line_first(self, heading: str, line: str) -> "ProjectFile":
        return self.with_body(heading, joined(line, self.body(heading), LINE_BREAK))

    def with_line_last(self, heading: str, line: str) -> "ProjectFile":
        return self.with_body(heading, joined(self.body(heading), line, LINE_BREAK))

    def with_block_last(self, heading: str, block: str) -> "ProjectFile":
        return self.with_body(heading, joined(self.body(heading), block, BLOCK_BREAK))

    def with_body(self, heading: str, body: str) -> "ProjectFile":
        rendered = joined(heading_line(heading), body.strip(), BLOCK_BREAK) + BLOCK_BREAK
        pattern = section_pattern(heading)
        if pattern.search(self._note.body):
            return self._with_text(pattern.sub(lambda _: rendered, self._note.body, count=1))
        return self._with_text(self._with_section_added(heading, rendered))

    def _with_text(self, body: str) -> "ProjectFile":
        return ProjectFile(self._note.with_body(body).text)

    def _with_section_added(self, heading: str, rendered: str) -> str:
        body = self._note.body
        project = section_pattern(PROJECT).search(body)
        if level_of(heading) == 1 or project:
            at = project.end() if project and level_of(heading) == 2 else self._markdown_end(body)
            return f"{body[:at].rstrip()}\n\n{rendered}{body[at:]}".strip() + LINE_BREAK
        at = self._markdown_end(body)
        return f"{body[:at].rstrip()}\n\n{heading_line(PROJECT)}\n\n{rendered}{body[at:]}".strip() + LINE_BREAK

    @staticmethod
    def _markdown_end(body: str) -> int:
        data = DATA_START_RE.search(body)
        return data.start() if data else len(body)
