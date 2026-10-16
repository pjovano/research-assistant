from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .linked_note import LinkedNote
from .project_file import BLOCK_BREAK, LINE_BREAK, joined, top_heading, top_heading_pattern
from .saved import save_text

WANTED, HELD = "Wanted", "Held"
QUESTIONS, SUBJECTS = "Questions", "Neighbouring subjects"
STATUSES = (HELD, WANTED)
LINE_SECTIONS = (QUESTIONS, SUBJECTS)
SECTIONS = (QUESTIONS, HELD, WANTED, SUBJECTS)
SECTION_BY_KIND = {"question": QUESTIONS, "held": HELD, "wanted": WANTED, "subject": SUBJECTS}
BOXED_SECTIONS = (SUBJECTS,)
PRIORITIES = ("high", "medium", "low")
NAME_SUFFIX = " - Reading list"
PROJECT = "project"
ENTRY_MARK = "- "
BOX_MARK = "- [ ] "
BOX_RE = re.compile(r"^- \[[ xX]\] ")
GROUP_MARK = "### "
UNGROUPED = ""
UNHELD_RE = re.compile(r"^- (?:\[[ xX]\] )?(?:\*\*(?P<priority>high|medium|low)\*\* · )?(?P<author>.+?) (?P<year>\d{4})[a-z]?, "
                       r"\*(?P<title>.+?)\*(?P<rest>.*)$")
BASENAME_RE = re.compile(r"^(?P<creator>.+?) - (?P<year>\d{4}) - (?P<title>.+)$")
APOSTROPHE_RE = re.compile(r"['\u2019]")
REASON_RE = re.compile(r"^\s*—\s*(?P<reason>.*?)(?:\s*\[[^\]]+\]\([^)]+\))?\s*$")
DISCOVER_TASK_RE = re.compile(r"^- \[[ xX]\] #discover · Discover “[^”]+”: \S")


def folded(text: str) -> str:
    plain = unicodedata.normalize("NFKD", APOSTROPHE_RE.sub("", text)).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", plain.lower()).split())


@dataclass(frozen=True)
class WantedWork:
    line: str
    author: str
    year: str
    title: str
    reason: str

    @classmethod
    def read(cls, line: str) -> "WantedWork | None":
        hit = UNHELD_RE.match(line)
        if hit is None:
            return None
        reason = REASON_RE.match(hit.group("rest"))
        return cls(line, hit.group("author"), hit.group("year"), hit.group("title"),
                   reason.group("reason") if reason else "")

    def is_held_as(self, basename: str) -> bool:
        held = BASENAME_RE.match(basename)
        if held is None or held.group("year") != self.year:
            return False
        mine, theirs = folded(self.title), folded(held.group("title"))
        surnames = [folded(part).split()[-1] for part in re.split(r",| and |&", self.author) if folded(part)]
        return (mine.startswith(theirs) or theirs.startswith(mine)) and surnames[0] in folded(held.group("creator"))

    def held_line(self, basename: str) -> str:
        return joined(f"{ENTRY_MARK}[[{basename}]]", self.reason, " — ")


def unmarked(line: str) -> str:
    return BOX_RE.sub("", line.strip(), count=1).removeprefix(ENTRY_MARK)


def marked(section: str, line: str) -> str:
    if section in BOXED_SECTIONS:
        return line if BOX_RE.match(line) else f"{BOX_MARK}{unmarked(line)}"
    return f"{ENTRY_MARK}{unmarked(line)}"


@dataclass(frozen=True)
class Place:
    section: str
    group: str = UNGROUPED


@dataclass(frozen=True)
class EntryShape:
    pattern: re.Pattern
    refusal: str

    def admits(self, line: str) -> bool:
        return self.pattern.match(line) is not None


ENTRY_SHAPES = {
    WANTED: EntryShape(UNHELD_RE, "a wanted entry reads **<high|medium|low>** · <Author> <Year>, *<Title>* — <reason>"),
    SUBJECTS: EntryShape(DISCOVER_TASK_RE, "a neighbouring subject reads - [ ] #discover · Discover “<Subject>”: <how it bears>"),
}


class StatusSection:
    def __init__(self, status: str, groups: dict[str, list[str]]) -> None:
        self._status = status
        self._groups = groups

    @classmethod
    def read(cls, status: str, text: str) -> "StatusSection":
        groups: dict[str, list[str]] = {UNGROUPED: []}
        group = UNGROUPED
        for line in text.splitlines():
            if line.startswith(GROUP_MARK):
                group = line[len(GROUP_MARK):].strip()
                groups.setdefault(group, [])
            elif line.startswith(ENTRY_MARK):
                groups[group].append(marked(status, line))
        return cls(status, groups)

    @property
    def text(self) -> str:
        blocks = [joined(GROUP_MARK + group if group else "", LINE_BREAK.join(lines), BLOCK_BREAK)
                  for group, lines in self._groups.items() if group or lines]
        return joined(top_heading(self._status), BLOCK_BREAK.join(blocks), BLOCK_BREAK)

    def entries(self) -> list[str]:
        return [line for lines in self._groups.values() for line in lines]

    def group_names(self) -> list[str]:
        return [group for group in self._groups if group]

    def in_order(self, group_names: list[str]) -> "StatusSection":
        named = {group: self._groups.get(group, []) for group in group_names}
        return StatusSection(self._status, {UNGROUPED: self._groups[UNGROUPED], **named})

    def group_of(self, line: str) -> str:
        return next((group for group, lines in self._groups.items() if line in lines), UNGROUPED)

    def with_entry(self, group: str, line: str) -> "StatusSection":
        groups = {name: list(lines) for name, lines in self._groups.items()}
        groups.setdefault(group, []).append(marked(self._status, line))
        return StatusSection(self._status, groups)

    def without_entry(self, line: str) -> "StatusSection":
        return StatusSection(self._status, {group: [each for each in lines if each != line]
                                            for group, lines in self._groups.items()})


class LineSection:
    def __init__(self, heading: str, lines: list[str]) -> None:
        self._heading = heading
        self._lines = lines

    @classmethod
    def read(cls, heading: str, text: str) -> "LineSection":
        return cls(heading, [marked(heading, line) for line in text.splitlines() if line.startswith(ENTRY_MARK)])

    @property
    def text(self) -> str:
        return joined(top_heading(self._heading), LINE_BREAK.join(self._lines), BLOCK_BREAK) if self._lines else ""

    def entries(self) -> list[str]:
        return list(self._lines)

    def group_names(self) -> list[str]:
        return []

    def in_order(self, group_names: list[str]) -> "LineSection":
        return self

    def with_entry(self, group: str, line: str) -> "LineSection":
        return LineSection(self._heading, [*self._lines, marked(self._heading, line)])


class ReadingList:
    def __init__(self, text: str) -> None:
        self._note = LinkedNote.parsed(text)
        self._sections = self._in_one_order({**{status: StatusSection.read(status, self._body_of(status))
                                                for status in STATUSES},
                                             **{name: LineSection.read(name, self._body_of(name))
                                                for name in LINE_SECTIONS}})

    @classmethod
    def blank(cls, project: str) -> "ReadingList":
        body = BLOCK_BREAK.join(top_heading(status) for status in STATUSES) + LINE_BREAK
        return cls(LinkedNote({PROJECT: f"[[{project}]]"}, body).text)

    @property
    def text(self) -> str:
        return self._note.text

    def entries(self, section: str) -> list[str]:
        return self._sections[section].entries()

    def group_of(self, status: str, line: str) -> str:
        return self._sections[status].group_of(line)

    def with_entry(self, place: Place, line: str) -> "ReadingList":
        return self._with_section(place.section, self._sections[place.section].with_entry(place.group, line))

    def without_entry(self, status: str, line: str) -> "ReadingList":
        return self._with_section(status, self._sections[status].without_entry(line))

    def now_held(self, basenames: list[str]) -> list[tuple[WantedWork, str]]:
        wanted = [work for line in self.entries(WANTED) if (work := WantedWork.read(line))]
        return [(work, basename) for work in wanted
                if (basename := next((each for each in basenames if work.is_held_as(each)), None))]

    def refreshed(self, basenames: list[str]) -> "ReadingList":
        moved = self
        for work, basename in self.now_held(basenames):
            place = Place(HELD, self.group_of(WANTED, work.line))
            moved = moved.without_entry(WANTED, work.line).with_entry(place, work.held_line(basename))
        return moved

    def _body_of(self, heading: str) -> str:
        hit = top_heading_pattern(heading).search(self._note.body)
        return hit.group(2) if hit else ""

    def _with_section(self, name: str, section: "StatusSection | LineSection") -> "ReadingList":
        sections = self._in_one_order({**self._sections, name: section})
        body = BLOCK_BREAK.join(text for each in SECTIONS if (text := sections[each].text)) + LINE_BREAK
        return ReadingList(self._note.with_body(body).text)

    @staticmethod
    def _in_one_order(sections: dict) -> dict:
        first_appearances = dict.fromkeys(group for status in STATUSES for group in sections[status].group_names())
        return {name: section.in_order(list(first_appearances)) for name, section in sections.items()}


class ReadingListFile:
    def __init__(self, directory: Path, project: str) -> None:
        self.project = project
        self.path = directory / f"{project}{NAME_SUFFIX}.md"

    def read(self) -> ReadingList:
        return ReadingList(self.path.read_text(encoding="utf-8")) if self.path.is_file() else ReadingList.blank(self.project)

    def create_if_absent(self) -> None:
        if not self.path.is_file():
            self.write(ReadingList.blank(self.project))

    def write(self, reading_list: ReadingList) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        save_text(self.path, reading_list.text)


class ProjectReadingLists:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def wanting(self) -> list[ReadingListFile]:
        return [file for file in self._files() if file.read().entries(WANTED)]

    def _files(self) -> list[ReadingListFile]:
        if not self._directory.is_dir():
            return []
        stems = sorted(path.stem for path in self._directory.glob(f"*{NAME_SUFFIX}.md"))
        return [ReadingListFile(self._directory, stem.removesuffix(NAME_SUFFIX)) for stem in stems]


class ReadingListReport:
    def __init__(self, file: ReadingListFile, basenames: list[str]) -> None:
        self._file = file
        self._basenames = basenames

    def as_json(self) -> dict:
        reading_list = self._file.read()
        return {"project": self._file.project, "file": str(self._file.path),
                **{kind: reading_list.entries(section) for kind, section in SECTION_BY_KIND.items()},
                "wanted_and_now_held": [{"entry": work.line, "held_as": basename}
                                        for work, basename in reading_list.now_held(self._basenames)]}


class ReadingListRefresh:
    def __init__(self, file: ReadingListFile, basenames: list[str]) -> None:
        self._file = file
        self._basenames = basenames

    def plan(self) -> dict:
        arrived = self._file.read().now_held(self._basenames)
        return {"project": self._file.project, "moved_to_held": [work.held_line(basename) for work, basename in arrived]}

    def apply(self) -> None:
        self._file.write(self._file.read().refreshed(self._basenames))


@dataclass(frozen=True)
class ReadingEntry:
    kind: str
    line: str
    group: str = UNGROUPED


class ReadingAddition:
    def __init__(self, file: ReadingListFile, entry: ReadingEntry) -> None:
        if entry.kind not in SECTION_BY_KIND:
            raise ValueError(f"a reading-list entry is one of {sorted(SECTION_BY_KIND)}")
        self._file = file
        self._place = Place(SECTION_BY_KIND[entry.kind], entry.group.strip())
        self._line = marked(self._place.section, f"{ENTRY_MARK}{unmarked(entry.line)}")
        self._refuse_an_entry_out_of_its_shape()
        self._refuse_an_entry_the_list_holds()

    def _refuse_an_entry_out_of_its_shape(self) -> None:
        shape = ENTRY_SHAPES.get(self._place.section)
        if shape is not None and not shape.admits(self._line):
            raise ValueError(shape.refusal)
        if self._place.group and self._place.section in LINE_SECTIONS:
            raise ValueError(f"an entry under {self._place.section} stands in no group")

    def _refuse_an_entry_the_list_holds(self) -> None:
        if unmarked(self._line) in [unmarked(held) for held in self._file.read().entries(self._place.section)]:
            raise ValueError(f"the reading list holds the entry under {self._place.section} already")

    def plan(self) -> dict:
        return {"project": self._file.project, "file": str(self._file.path), "section": self._place.section,
                "group": self._place.group, "line": self._line}

    def apply(self) -> None:
        self._file.write(self._file.read().with_entry(self._place, self._line))
