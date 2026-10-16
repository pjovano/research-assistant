from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from functools import cached_property
from pathlib import Path

from vault import FOOTNOTE_DEFINITION_RE, OBSIDIAN_COMMENT_RE, WIKILINK_RE, parse_note

from .docx_style import DocxStyle, ReferenceDocument
from .pandoc import Pandoc
from .tree import Project

DOCX_SUFFIX = ".docx"
EMBED_RE = re.compile(r"!\[\[[^\]]*\]\]")
IMAGE_RE = re.compile(r"!\[")
TRASH_EXECUTABLE = "trash"
LINE_FEED = "\n"


class InboxDocx:
    def __init__(self, inbox: Path, filename: str) -> None:
        self._path = inbox / Path(filename).name

    def checked(self) -> Path:
        if self._path.suffix.lower() != DOCX_SUFFIX:
            raise ValueError(f"{self._path.name} is not a {DOCX_SUFFIX} file")
        if not self._path.is_file():
            raise ValueError(f"no file named {self._path.name} in {self._path.parent}")
        return self._path


class WordFile:
    def __init__(self, path: Path, pandoc: Pandoc) -> None:
        self.path = path
        self._pandoc = pandoc

    def markdown(self) -> str:
        return LINE_FEED.join(self._pandoc.markdown_of(self.path).splitlines()) + LINE_FEED


class DocxImport:
    def __init__(self, project: Project, section: str | None, word_file: WordFile) -> None:
        self._project = project
        self._word_file = word_file
        self._target = project.drafts.next(section)

    def plan(self) -> dict:
        return {"project": self._project.name, "draft": str(self._path()), "converted_from": str(self._word_file.path),
                "words": len(self._markdown.split()),
                "footnotes": sum(1 for line in self._markdown.splitlines() if FOOTNOTE_DEFINITION_RE.match(line)),
                "images_not_carried": len(IMAGE_RE.findall(self._markdown))}

    def apply(self) -> None:
        path = self._path()
        if path.exists():
            raise ValueError(f"{path} exists: a draft is never overwritten")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._markdown, encoding="utf-8", newline=LINE_FEED)
        self._project.list_first_under_drafts(self._target.basename)

    def _path(self) -> Path:
        return self._project.drafts.path(self._target)

    @cached_property
    def _markdown(self) -> str:
        return self._word_file.markdown()


class Trash:
    def take(self, path: Path) -> None:
        executable = shutil.which(TRASH_EXECUTABLE)
        if executable is None:
            raise ValueError(f"this machine has no `{TRASH_EXECUTABLE}` command: {path} stays where it is")
        try:
            subprocess.run([executable, str(path)], capture_output=True, check=True, text=True)
        except subprocess.CalledProcessError as failure:
            raise ValueError(f"{path} could not be moved to the Trash: {failure.stderr.strip()}") from failure


class DocxDiscard:
    def __init__(self, docx: Path, trash: Trash) -> None:
        self._docx = docx
        self._trash = trash

    def plan(self) -> dict:
        return {"moved_to_trash": str(self._docx)}

    def apply(self) -> None:
        self._trash.take(self._docx)


class ExportText:
    def __init__(self, note_text: str) -> None:
        self._body = parse_note(note_text)[1]

    def markdown(self) -> str:
        without_comments = OBSIDIAN_COMMENT_RE.sub("", self._body)
        without_embeds = EMBED_RE.sub("", without_comments)
        return WIKILINK_RE.sub(self._shown, without_embeds)

    @staticmethod
    def _shown(link: re.Match) -> str:
        return link.group("shown") or link.group("target").strip()


class StyledDocx:
    def __init__(self, style: DocxStyle, pandoc: Pandoc) -> None:
        self.style = style
        self._pandoc = pandoc

    def write(self, markdown: str, target: Path) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            self._pandoc.write_docx(markdown, self.reference_in(Path(scratch)), target)

    def reference_in(self, scratch: Path) -> Path:
        reference = scratch / "reference.docx"
        ReferenceDocument(self._pandoc.default_reference(), self.style).save(reference)
        return reference


class DocxExport:
    def __init__(self, note: Path, directory: Path, styled: StyledDocx) -> None:
        self._note = note
        self._styled = styled
        self._target = directory / f"{note.stem}{DOCX_SUFFIX}"
        if self._target.exists():
            raise ValueError(f"{self._target} exists: name another directory")

    def plan(self) -> dict:
        return {"note": str(self._note), "docx": str(self._target), "style": self._styled.style.name}

    def apply(self) -> None:
        self._target.parent.mkdir(parents=True, exist_ok=True)
        self._styled.write(ExportText(self._note.read_text(encoding="utf-8")).markdown(), self._target)
