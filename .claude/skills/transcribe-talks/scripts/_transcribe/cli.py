from __future__ import annotations

import argparse
import json
import sys

from .checking import VERDICT_PASSED, ReviewCheck
from .commands import Subprocess, ToolFailed
from .diarizing import DiarizationUnavailable, PyannotePipeline, SpeakerTurns
from .fetching import AudioFetch
from .filing import FilingRefused, TalkFiling
from .listing import ReviewListing
from .merging import SpeakerAssignment
from .playlist import HeldTalks, PlaylistListing, PlaylistReport
from .raw import RawTranscript
from .settings import TalkSettings
from .talk import Talks
from .whispering import WhisperRun

_DESCRIPTION = ("Transcribe -- fetch a recorded talk's audio, transcribe it with its speakers, list it for the "
                "transcript reviewer, check the review, and file the transcript with its Zotero record.")
EXIT_FAILURE = 1


def main() -> None:
    args = CommandLine(Commands()).parse()
    try:
        args.func(args)
    except (ToolFailed, DiarizationUnavailable, FilingRefused, LookupError) as error:
        _print({"error": str(error)})
        sys.exit(EXIT_FAILURE)


class Commands:
    def fetch(self, args: argparse.Namespace) -> None:
        if not args.playlist and not args.urls:
            raise ToolFailed("fetch takes one or more URLs, or --playlist")
        urls = self._new_playlist_urls() if args.playlist else args.urls
        if not urls:
            _print({"fetched": [], "note": "the playlist holds no new talk"})
            return
        fetched = AudioFetch(urls, TalkSettings(), Subprocess()).run()
        _print({"fetched": [entry.summary() for entry in fetched]})

    def playlist(self, args: argparse.Namespace) -> None:
        _print(self._playlist_report().as_dict())

    def _new_playlist_urls(self) -> list[str]:
        return [video.url for video in self._playlist_report().new_videos()]

    @staticmethod
    def _playlist_report() -> PlaylistReport:
        return PlaylistReport(PlaylistListing(TalkSettings(), Subprocess()).videos(), HeldTalks())

    def transcribe(self, args: argparse.Namespace) -> None:
        entry = Talks.named(args.video_id)
        settings = TalkSettings()
        segments = WhisperRun(entry, settings, Subprocess()).run(args.language)
        turns = SpeakerTurns(entry, PyannotePipeline(settings.diarization_model)).run()
        utterances = SpeakerAssignment(segments, turns).utterances()
        RawTranscript(entry.raw).write(utterances)
        entry.discard_audio()
        _print({**entry.summary(), "segments": len(segments), "turns": len(turns), "utterances": len(utterances),
                "speakers": sorted({turn.speaker for turn in turns}), "raw": str(entry.raw)})

    def review_listing(self, args: argparse.Namespace) -> None:
        entry = Talks.named(args.video_id)
        listing = ReviewListing(entry)
        path = listing.write()
        parts = listing.as_dict()["parts"]
        _print({"video_id": entry.video_id, "listing": str(path), "parts": len(parts),
                "words": sum(part["words"] for part in parts), "card": str(entry.card)})

    def review_check(self, args: argparse.Namespace) -> None:
        report = ReviewCheck(Talks.named(args.video_id)).report()
        _print(report)
        if report["verdict"] != VERDICT_PASSED:
            sys.exit(EXIT_FAILURE)

    def file(self, args: argparse.Namespace) -> None:
        filing = TalkFiling(Talks.named(args.video_id))
        _print(filing.apply() if args.apply else filing.plan())

    def status(self, args: argparse.Namespace) -> None:
        _print({"talks": [entry.summary() for entry in Talks.all()]})


class CommandLine:
    def __init__(self, commands: Commands) -> None:
        self._commands = commands

    def parse(self) -> argparse.Namespace:
        parser = argparse.ArgumentParser(prog="transcribe.py", description=_DESCRIPTION)
        subcommands = parser.add_subparsers(dest="command", required=True)
        self._add_fetch(subcommands)
        self._add_transcribe(subcommands)
        for command in self._review_commands():
            self._add_by_id(subcommands, command)
        self._add_file(subcommands)
        subcommands.add_parser("status", help="every fetched talk with its stage").set_defaults(
            func=self._commands.status)
        return parser.parse_args()

    def _add_fetch(self, subcommands) -> None:
        fetch = subcommands.add_parser("fetch", help="download the audio and the record of each URL, a playlist "
                                                     "URL expanding to every talk in it; with --playlist and no "
                                                     "URL, the new talks of the playlist machine.json names")
        fetch.add_argument("urls", nargs="*")
        fetch.add_argument("--playlist", action="store_true")
        fetch.set_defaults(func=self._commands.fetch)
        subcommands.add_parser("playlist", help="every video of the playlist machine.json names, each held, "
                                                "in progress, or new").set_defaults(func=self._commands.playlist)

    def _add_transcribe(self, subcommands) -> None:
        transcribe = subcommands.add_parser("transcribe", help="transcribe one fetched talk with its speakers, then "
                                                               "delete its audio")
        transcribe.add_argument("video_id")
        transcribe.add_argument("--language", help="the talk's language as a code, e.g. de; detected when absent")
        transcribe.set_defaults(func=self._commands.transcribe)

    def _review_commands(self) -> tuple[tuple[str, object, str], ...]:
        return (("review-listing", self._commands.review_listing,
                 "write the review listing for the transcript reviewer"),
                ("review-check", self._commands.review_check,
                 "check the reviewed parts and the talk card; exit 1 if the review failed"))

    @staticmethod
    def _add_by_id(subcommands, command: tuple[str, object, str]) -> None:
        name, handler, help_text = command
        parser = subcommands.add_parser(name, help=help_text)
        parser.add_argument("video_id")
        parser.set_defaults(func=handler)

    def _add_file(self, subcommands) -> None:
        file = subcommands.add_parser("file", help="create the Zotero record and write the transcript into the "
                                                   "vault; without --apply, print the plan")
        file.add_argument("video_id")
        file.add_argument("--apply", action="store_true")
        file.set_defaults(func=self._commands.file)


def _print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
