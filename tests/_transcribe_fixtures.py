from __future__ import annotations

import json
import unittest
from dataclasses import dataclass

from _support import LiveTree

LiveTree.activate()

import transcribe
from _vaults import TempVault

VIDEO_ID = "abc123xyz"
RECORDING_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
INFO = {
    "id": VIDEO_ID,
    "title": "Hegel on Logic as Metaphysics: A Lecture",
    "channel": "Philosophy Talks",
    "upload_date": "20190314",
    "description": "Robert Pippin lectures on the Science of Logic. https://example.org/x",
    "duration": 3725,
    "webpage_url": RECORDING_URL,
    "chapters": [{"title": "Talk", "start_time": 0.0}, {"title": "Q&A", "start_time": 2400.0}],
}
WHISPER_JSON = {
    "result": {"language": "en"},
    "transcription": [
        {"timestamps": {"from": "00:00:00,000", "to": "00:00:04,000"}, "offsets": {"from": 0, "to": 4000},
         "text": " Thank you for the introduction."},
        {"timestamps": {"from": "00:00:04,000", "to": "00:00:09,000"}, "offsets": {"from": 4000, "to": 9000},
         "text": " Logic, for Hegel, is metaphysics."},
        {"timestamps": {"from": "00:40:00,000", "to": "00:40:05,000"}, "offsets": {"from": 2400000, "to": 2405000},
         "text": " May I ask about the doctrine of essence?"},
        {"timestamps": {"from": "00:40:05,000", "to": "00:40:09,000"}, "offsets": {"from": 2405000, "to": 2409000},
         "text": "   "},
    ],
}
TURNS = [transcribe.Turn(0, 10000, "SPEAKER_00"), transcribe.Turn(2399000, 2410000, "SPEAKER_01")]
RAW_TEXT = ("%% 00:00:00 %%\n**SPEAKER_00:** Thank you for the introduction. Logic, for Hegel, is metaphysics.\n\n"
            "%% 00:40:00 %%\n**SPEAKER_01:** May I ask about the doctrine of essence?\n")
REVIEWED_TEXT = ("## Talk\n\n%% 00:00:00 %%\n**Pippin:** Logic, for Hegel, is metaphysics.\n\n"
                 "## Discussion\n\n%% 00:40:00 %%\n**Audience member:** May I ask about the doctrine of essence?\n")
CARD = {"title": "Hegel on Logic as Metaphysics", "presenters": [{"firstName": "Robert", "lastName": "Pippin"}],
        "year": 2019, "meeting": "Philosophy Talks lecture series", "dropped": "the chair's introduction"}
BASENAME = "Pippin - 2019 - Hegel on Logic as Metaphysics"
FILLER = " ".join(["word"] * transcribe.MAX_PART_WORDS) + "."
TWO_PART_RAW = (f"%% 00:00:00 %%\n**SPEAKER_00:** {FILLER}\n\n"
                "%% 00:40:00 %%\n**SPEAKER_01:** May I ask about the doctrine of essence?\n")
TALK_PART = f"## Talk\n\n%% 00:00:00 %%\n**Pippin:** {FILLER}"


@dataclass(frozen=True)
class Review:
    parts: tuple[str, ...] = (REVIEWED_TEXT,)
    card: dict | None = None
    raw: str = RAW_TEXT


class RecordedRunner:
    def __init__(self, on_run=None) -> None:
        self.commands: list[list[str]] = []
        self._on_run = on_run

    def run(self, arguments: list[str]) -> str:
        self.commands.append(arguments)
        if self._on_run is not None:
            self._on_run(arguments)
        return ""


class TalkTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("CORPUS_DIR", "TRANSCRIPTS_DIR").activate()
        self.addCleanup(self.vault.discard)

    def fetched(self, video_id: str = VIDEO_ID, **info) -> transcribe.TalkEntry:
        entry = transcribe.TalkEntry(video_id)
        entry.directory.mkdir(parents=True)
        entry.info.write_text(json.dumps({**INFO, "id": video_id, **info}), encoding="utf-8")
        entry.audio.write_bytes(b"RIFF")
        return entry

    def transcribed(self, video_id: str = VIDEO_ID, raw: str = RAW_TEXT) -> transcribe.TalkEntry:
        entry = self.fetched(video_id)
        entry.raw.write_text(raw, encoding="utf-8")
        entry.audio.unlink()
        return entry

    def reviewed(self, video_id: str = VIDEO_ID, review: Review = Review()) -> transcribe.TalkEntry:
        entry = self.transcribed(video_id, review.raw)
        entry.reviewed_dir.mkdir()
        for number, text in enumerate(review.parts, start=1):
            entry.part_path(number).write_text(text, encoding="utf-8")
        entry.card.write_text(json.dumps(CARD if review.card is None else review.card), encoding="utf-8")
        return entry
