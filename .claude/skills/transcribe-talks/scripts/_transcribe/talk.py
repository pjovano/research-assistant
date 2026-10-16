from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import vault

TALKS_DIR_NAME = "talks"
AUDIO_NAME = "audio.wav"
INFO_NAME = "audio.info.json"
SEGMENTS_NAME = "segments.json"
TURNS_NAME = "turns.json"
RAW_NAME = "raw.md"
LISTING_NAME = "listing.json"
REVIEWED_DIR_NAME = "reviewed"
CARD_NAME = "card.json"
SAVED_ITEM_NAME = "zotero-item.json"
PART_NAME = "part-{number:02d}.md"
PART_GLOB = "part-*.md"

STAGE_ABSENT = "absent"
STAGE_FETCHED = "fetched"
STAGE_TRANSCRIBED = "transcribed"
STAGE_REVIEWED = "reviewed"

_ENCODING = "utf-8"
_UPLOAD_DATE_LENGTH = 8


def talks_dir() -> Path:
    return vault.SCRATCH_DIR / TALKS_DIR_NAME


@dataclass(frozen=True)
class Recording:
    video_id: str
    title: str
    channel: str
    upload_date: str
    description: str
    duration_seconds: int
    url: str
    chapters: tuple[dict, ...]

    @staticmethod
    def read(path: Path) -> "Recording":
        info = json.loads(path.read_text(encoding=_ENCODING))
        return Recording(
            video_id=str(info.get("id", "")),
            title=str(info.get("title", "")),
            channel=str(info.get("channel") or info.get("uploader") or ""),
            upload_date=_iso_date(str(info.get("upload_date") or "")),
            description=str(info.get("description") or ""),
            duration_seconds=int(info.get("duration") or 0),
            url=str(info.get("webpage_url") or info.get("original_url") or ""),
            chapters=tuple(_chapter(entry) for entry in info.get("chapters") or []),
        )

    @property
    def year(self) -> int | None:
        return int(self.upload_date[:4]) if self.upload_date else None

    def as_dict(self) -> dict:
        return {"video_id": self.video_id, "title": self.title, "channel": self.channel,
                "upload_date": self.upload_date, "description": self.description,
                "duration_seconds": self.duration_seconds, "url": self.url, "chapters": list(self.chapters)}


def _iso_date(compact: str) -> str:
    if len(compact) != _UPLOAD_DATE_LENGTH or not compact.isdigit():
        return ""
    return f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"


def _chapter(entry: dict) -> dict:
    return {"title": str(entry.get("title", "")), "start_seconds": int(entry.get("start_time") or 0)}


class TalkEntry:
    def __init__(self, video_id: str) -> None:
        self.video_id = video_id
        self.directory = talks_dir() / video_id

    @property
    def audio(self) -> Path:
        return self.directory / AUDIO_NAME

    @property
    def info(self) -> Path:
        return self.directory / INFO_NAME

    @property
    def segments(self) -> Path:
        return self.directory / SEGMENTS_NAME

    @property
    def turns(self) -> Path:
        return self.directory / TURNS_NAME

    @property
    def raw(self) -> Path:
        return self.directory / RAW_NAME

    @property
    def listing(self) -> Path:
        return self.directory / LISTING_NAME

    @property
    def reviewed_dir(self) -> Path:
        return self.directory / REVIEWED_DIR_NAME

    @property
    def card(self) -> Path:
        return self.directory / CARD_NAME

    @property
    def saved_item(self) -> Path:
        return self.directory / SAVED_ITEM_NAME

    def part_path(self, number: int) -> Path:
        return self.reviewed_dir / PART_NAME.format(number=number)

    def reviewed_parts(self) -> list[Path]:
        if not self.reviewed_dir.is_dir():
            return []
        return sorted(self.reviewed_dir.glob(PART_GLOB))

    def recording(self) -> Recording:
        return Recording.read(self.info)

    def stage(self) -> str:
        if self.card.exists():
            return STAGE_REVIEWED
        if self.raw.exists():
            return STAGE_TRANSCRIBED
        if self.info.exists():
            return STAGE_FETCHED
        return STAGE_ABSENT

    def summary(self) -> dict:
        summary = {"video_id": self.video_id, "stage": self.stage(), "directory": str(self.directory)}
        if self.info.exists():
            recording = self.recording()
            summary.update({"title": recording.title, "channel": recording.channel,
                            "duration_seconds": recording.duration_seconds, "url": recording.url})
        return summary

    def discard_audio(self) -> None:
        self.audio.unlink(missing_ok=True)

    def delete(self) -> None:
        shutil.rmtree(self.directory)


class Talks:
    @staticmethod
    def all() -> list[TalkEntry]:
        directory = talks_dir()
        if not directory.is_dir():
            return []
        return [TalkEntry(path.name) for path in sorted(directory.iterdir()) if path.is_dir()]

    @staticmethod
    def named(video_id: str) -> TalkEntry:
        entry = TalkEntry(video_id)
        if entry.stage() == STAGE_ABSENT:
            raise LookupError(f"no fetched talk {video_id!r} in {talks_dir()}")
        return entry
