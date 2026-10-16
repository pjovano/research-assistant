from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pagetext
import pymupdf
import vault
from vault import ReplacementFile

from .analysis import PdfAnalysis
from .cleaning import InPlaceClean
from .covers import CoverImage, CoverPage
from .entries import OutlineProposal
from .fontfilter import FontFilter, FontReport, OutlineSuggestion
from .inspection import OutlineDiff
from .outline import Outline
from .paths import PdfLocation, ScratchOutput
from .render import FIRST_PAGE, FilePage, PageRender
from .report import Report
from .toc import TocDocument

COVER_TEMPORARY_SUFFIX = ".cover.tmp.pdf"
DROP_TEMPORARY_SUFFIX = ".drop.tmp.pdf"


class CleanCommands:
    def plan(self, args: argparse.Namespace) -> None:
        Report([PdfAnalysis(p).report_with_preview() for p in self._targets(args)]).print()

    def clean(self, args: argparse.Namespace) -> None:
        pdf_path = PdfLocation(args.pdf).in_inbox()
        report = PdfAnalysis(pdf_path).report_with_preview()
        if not args.apply:
            Report(report).print_as_dry_run("rewrite the inbox file in place")
            return
        self._clean_in_place(pdf_path, report["item_type"])

    def _targets(self, args: argparse.Namespace) -> list[Path]:
        if args.all:
            return vault.list_pdfs(vault.INBOX_DIR)
        return [PdfLocation(args.pdf).in_inbox()]

    def _clean_in_place(self, pdf_path: Path, item_type: str) -> None:
        cleaning = InPlaceClean(pdf_path)
        cleaning.run()
        result = {"written": str(pdf_path), "item_type": item_type}
        if cleaning.repaired_with_qpdf():
            result["repaired_with_qpdf"] = True
        Report(result).print()


class VolumeCommands:
    def move(self, args: argparse.Namespace) -> None:
        source = PdfLocation(args.pdf).in_inbox()
        self._require_outline(source)
        destination = self._free_destination(source.name)
        if not args.apply:
            plan = {"move": str(source), "to": str(destination), "pages": TocDocument(source).page_count()}
            Report(plan).print_as_dry_run("move the inbox file among the volumes")
            return
        self._move(source, destination)
        Report({"moved": str(destination)}).print()

    def _move(self, source: Path, destination: Path) -> None:
        vault.VOLUMES_DIR.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))

    def _free_destination(self, name: str) -> Path:
        destination = vault.VOLUMES_DIR / name
        if destination.exists():
            raise SystemExit(f"Already among the volumes: {name}")
        return destination

    @staticmethod
    def _require_outline(source: Path) -> None:
        if pagetext.outline_entries(source):
            return
        raise SystemExit(
            f"{source.name} carries no outline, and a volume's bookmarks are its contents: "
            "bookmark it with toc write --apply before moving it, and it has not been moved.")


class PageCommands:
    def render(self, args: argparse.Namespace) -> None:
        pdf_path = PdfLocation(args.pdf).anywhere()
        Report({"render": str(PageRender(pdf_path).save(args.page))}).print()

    def add_cover(self, args: argparse.Namespace) -> None:
        pdf_path = PdfLocation(args.pdf).in_inbox()
        image = CoverImage(Path(args.image)).require_exists().trimmed(args.crop_top, args.crop_bottom)
        if not args.force:
            self._require_cover_applies(pdf_path)
        if not args.apply:
            Report(self._cover_plan(pdf_path, image)).print_as_dry_run("prepend the cover to the inbox file")
            return
        self._prepend_cover(pdf_path, image)
        Report({"cover_added": str(pdf_path), "image": str(image.path)}).print()

    def drop_page(self, args: argparse.Namespace) -> None:
        pdf_path = PdfLocation(args.pdf).in_inbox()
        before = TocDocument(pdf_path).page_count()
        FilePage(args.page, before, pdf_path.name).require_in_range()
        if not args.apply:
            plan = {"drop_page": args.page, **self._page_counts(before)}
            Report(plan).print_as_dry_run("delete the page from the inbox file")
            return
        self._drop(pdf_path, args.page, before)
        Report({"dropped_page": args.page, **self._page_counts(before)}).print()

    def _require_cover_applies(self, pdf_path: Path) -> None:
        analysis = PdfAnalysis(pdf_path)
        analysis.require_book()
        analysis.require_no_cover()

    def _cover_plan(self, pdf_path: Path, image: CoverImage) -> dict:
        before = TocDocument(pdf_path).page_count()
        return {"add_cover": str(pdf_path), "image": str(image.path),
                "pages_before": before, "pages_after": before + 1}

    def _page_counts(self, before: int) -> dict:
        return {"pages_before": before, "pages_after": before - 1}

    def _prepend_cover(self, pdf_path: Path, image: CoverImage) -> None:
        with ReplacementFile(pdf_path, COVER_TEMPORARY_SUFFIX) as replacement:
            with pymupdf.open(pdf_path) as doc:
                CoverPage(doc).prepend(image)
                doc.save(replacement.path)
            replacement.commit()

    def _drop(self, pdf_path: Path, page: int, before: int) -> None:
        with ReplacementFile(pdf_path, DROP_TEMPORARY_SUFFIX) as replacement:
            self._drop_into(replacement.path, pdf_path, page)
            self._verify_dropped(replacement.path, before)
            replacement.commit()

    def _drop_into(self, partial: Path, pdf_path: Path, page: int) -> None:
        with pymupdf.open(pdf_path) as doc:
            doc.delete_page(page - FIRST_PAGE)
            doc.save(partial)

    def _verify_dropped(self, tmp: Path, before: int) -> None:
        expected = before - 1
        with pymupdf.open(tmp) as check:
            if check.page_count != expected:
                raise SystemExit(
                    f"Refusing to keep {tmp.name}: expected {expected} pages, got {check.page_count}.")


class TocCommands:
    def probe(self, args: argparse.Namespace) -> None:
        Report(TocDocument(PdfLocation(args.pdf).anywhere()).probe()).print()

    def scan(self, args: argparse.Namespace) -> None:
        document = TocDocument(PdfLocation(args.pdf).anywhere())
        renders = document.scan(args.first, args.last, args.dpi)
        Report({"dpi": args.dpi, "pages": renders}).print()

    def fonts(self, args: argparse.Namespace) -> None:
        Report(FontReport(PdfLocation(args.pdf).anywhere(), args.page).as_dict()).print()

    def suggest(self, args: argparse.Namespace) -> None:
        filters = [FontFilter.parsed(spec) for spec in args.filter]
        entries = OutlineSuggestion(PdfLocation(args.pdf).anywhere(), filters).outline().as_dicts()
        if args.out:
            self._save_entries(args.out, entries)
        Report(entries).print()

    def write(self, args: argparse.Namespace) -> None:
        document = TocDocument(PdfLocation(args.pdf).anywhere())
        proposal = OutlineProposal(args.entries, document.page_count())
        proposed = proposal.outline_allowing_empty() if args.force else proposal.outline()
        if args.apply:
            self._write_outline(document, proposed)
        else:
            self._preview_outline(document, proposed)

    def clear(self, args: argparse.Namespace) -> None:
        if not args.apply:
            raise SystemExit("toc clear destroys the outline and has no dry run; pass --apply.")
        document = TocDocument(PdfLocation(args.pdf).anywhere())
        destroyed = len(document.outline().entries())
        document.clear()
        Report({"cleared": str(document.path), "entries_destroyed": destroyed}).print()

    def _save_entries(self, given: str, entries: list[dict]) -> None:
        destination = ScratchOutput(given).path()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _diff(self, document: TocDocument, proposed: Outline) -> dict:
        return OutlineDiff(document.outline(), proposed).as_dict()

    def _preview_outline(self, document: TocDocument, proposed: Outline) -> None:
        diff = self._diff(document, proposed)
        Report({"entries": proposed.as_dicts(), "diff": diff}).print_as_dry_run(
            "write the outline into the file")

    def _write_outline(self, document: TocDocument, proposed: Outline) -> None:
        diff = self._diff(document, proposed)
        document.write(proposed)
        Report({"written": str(document.path), "diff": diff,
                 "entries": document.outline().as_dicts()}).print()
