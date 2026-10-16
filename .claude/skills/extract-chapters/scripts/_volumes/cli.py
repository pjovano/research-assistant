from __future__ import annotations

import argparse
import json
import sys

from .apparatus_ranges import VolumeApparatus
from .contents import HeldVolumes, VolumeContents
from .document import VolumeDocument
from .extraction import AppendedRange, ChapterExtraction, ChosenChapter, PageRange

DEFAULT_CHAPTER_LEVEL = 1
NO_OUTLINE_ERROR = {"error": "no outline: bookmark the volume first"}
DRY_RUN_NOTICE = "\n(dry run -- pass --apply to write the PDF into the inbox)"
OUTLINE_PRESENT = "present"
OUTLINE_ABSENT = "absent"
FAILURE_EXIT = 1


class CommandLine:
    def __init__(self) -> None:
        self._parser = argparse.ArgumentParser()
        self._volumes = HeldVolumes()
        self._add_commands()

    def run(self) -> None:
        args = self._parser.parse_args()
        try:
            args.handler(args)
        except ValueError as failure:
            raise SystemExit(str(failure)) from failure

    def _add_commands(self) -> None:
        sub = self._parser.add_subparsers(dest="command", required=True)
        self._add_list(sub)
        self._add_contents(sub)
        self._add_extract(sub)

    def _add_list(self, sub) -> None:
        command = sub.add_parser("list", help="read-only: every held volume, with its chapter count")
        command.set_defaults(handler=self._list)

    def _add_contents(self, sub) -> None:
        command = sub.add_parser("contents", help="read-only: a volume's chapters and its apparatus")
        command.add_argument("volume", help="a PDF in the volumes directory, by name or path")
        command.add_argument("--level", type=int, default=DEFAULT_CHAPTER_LEVEL,
                             help="deepest outline level listed as a chapter (default 1)")
        command.set_defaults(handler=self._contents)

    def _add_extract(self, sub) -> None:
        command = sub.add_parser("extract", help="copy a chapter of a volume into the inbox")
        command.add_argument("volume", help="a PDF in the volumes directory, by name or path")
        command.add_argument("--range", required=True, help="file pages <first>-<last>, 1-based")
        command.add_argument("--title", required=True, help="the chapter title; names the new PDF")
        command.add_argument("--also", action="append", default=[], metavar="A-B",
                             help="a further file-page range to append; repeatable")
        command.add_argument("--no-apparatus", action="store_true",
                             help="do not append the volume's collected bibliography or endnotes")
        command.add_argument("--apply", action="store_true",
                             help="write the PDF; without it, report the plan and write nothing")
        command.set_defaults(handler=self._extract)

    def _list(self, args: argparse.Namespace) -> None:
        self._print([self._row(VolumeDocument.read(pdf)) for pdf in self._volumes.pdfs()])

    def _row(self, volume: VolumeDocument) -> dict:
        contents = VolumeContents(volume, max_level=DEFAULT_CHAPTER_LEVEL)
        outline = OUTLINE_PRESENT if volume.has_outline() else OUTLINE_ABSENT
        return {"volume": volume.basename, "page_count": volume.page_count, "outline": outline,
                "chapters": len(contents.chapters()), "apparatus": self._apparatus_json(volume)}

    def _contents(self, args: argparse.Namespace) -> None:
        volume = self._bookmarked(args.volume)
        contents = VolumeContents(volume, max_level=args.level)
        self._print({**contents.as_json(), "apparatus": self._apparatus_json(volume)})

    def _extract(self, args: argparse.Namespace) -> None:
        volume = self._bookmarked(args.volume)
        chapter = PageRange.parse(args.range)
        appended = self._appended_for(volume, chapter, args)
        extraction = ChapterExtraction(volume, ChosenChapter(chapter, args.title, tuple(appended)))
        if args.apply:
            extraction.write()
            self._print({**extraction.plan(), "written": str(extraction.destination)})
            return
        self._print(extraction.plan())
        print(DRY_RUN_NOTICE, file=sys.stderr)

    def _bookmarked(self, argument: str) -> VolumeDocument:
        volume = VolumeDocument.read(self._volumes.resolve(argument))
        if volume.has_outline():
            return volume
        self._print(NO_OUTLINE_ERROR)
        raise SystemExit(FAILURE_EXIT)

    def _appended_for(self, volume: VolumeDocument, chapter: PageRange,
                      args: argparse.Namespace) -> list[AppendedRange]:
        named = [AppendedRange("also", PageRange.parse(text)) for text in args.also]
        if args.no_apparatus:
            return named
        return named + self._apparatus_ranges(volume, chapter, named)

    def _apparatus_ranges(self, volume: VolumeDocument, chapter: PageRange,
                          named: list[AppendedRange]) -> list[AppendedRange]:
        taken = [chapter] + [item.page_range for item in named]
        found = []
        for section in VolumeApparatus(volume).sections():
            if any(section.covers(page_range) for page_range in taken):
                continue
            found.append(AppendedRange(f"{section.kind}: {section.title}", section.pages))
        return found

    @staticmethod
    def _apparatus_json(volume: VolumeDocument) -> list[dict]:
        return [section.as_json() for section in VolumeApparatus(volume).sections()]

    @staticmethod
    def _print(payload) -> None:
        print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    CommandLine().run()
