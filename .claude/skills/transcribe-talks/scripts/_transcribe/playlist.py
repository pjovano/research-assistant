from __future__ import annotations

import json
import re
from dataclasses import dataclass

import vault

from .commands import Subprocess, ToolFailed
from .filing import recording_url_of
from .settings import TALKS_PLAYLIST_KEY, TalkSettings
from .talk import Talks

STATUS_HELD = "held"
STATUS_IN_PROGRESS = "in progress"
STATUS_NEW = "new"
WATCH_URL = "https://www.youtube.com/watch?v={video_id}"
LISTING_ARGUMENTS = ("--flat-playlist", "-J")
_VIDEO_ID_RE = re.compile(r"(?:[?&]v=|youtu\.be/|/shorts/|/live/|/embed/)(?P<id>[A-Za-z0-9_-]{11})")


@dataclass(frozen=True)
class PlaylistVideo:
    video_id: str
    title: str
    duration_seconds: int

    @property
    def url(self) -> str:
        return WATCH_URL.format(video_id=self.video_id)

    def as_dict(self) -> dict:
        return {"video_id": self.video_id, "title": self.title, "duration_seconds": self.duration_seconds,
                "url": self.url}


def video_id_of(url: str) -> str | None:
    match = _VIDEO_ID_RE.search(url)
    return match.group("id") if match else None


class PlaylistListing:
    def __init__(self, settings: TalkSettings, runner: Subprocess) -> None:
        self._settings = settings
        self._runner = runner

    def videos(self) -> list[PlaylistVideo]:
        payload = json.loads(self._runner.run(self.command()))
        entries = (entry for entry in payload.get("entries") or [] if entry and entry.get("id"))
        return [PlaylistVideo(str(entry["id"]), str(entry.get("title") or ""), int(entry.get("duration") or 0))
                for entry in entries]

    def command(self) -> list[str]:
        playlist = self._settings.playlist
        if playlist is None:
            raise ToolFailed(f"machine.json names no {TALKS_PLAYLIST_KEY}; name the playlist's URL under it")
        return [self._settings.yt_dlp, *LISTING_ARGUMENTS, playlist]


class HeldTalks:
    def held_ids(self) -> set[str]:
        urls = (recording_url_of(vault.read_frontmatter(path)[1]) for path in vault.list_transcripts())
        ids = (video_id_of(url) for url in urls if url)
        return {video_id for video_id in ids if video_id}

    @staticmethod
    def entry_ids() -> set[str]:
        return {entry.video_id for entry in Talks.all()}


class PlaylistReport:
    def __init__(self, videos: list[PlaylistVideo], held: HeldTalks) -> None:
        self._videos = videos
        self._held_ids = held.held_ids()
        self._entry_ids = held.entry_ids()

    def status_of(self, video: PlaylistVideo) -> str:
        if video.video_id in self._held_ids:
            return STATUS_HELD
        if video.video_id in self._entry_ids:
            return STATUS_IN_PROGRESS
        return STATUS_NEW

    def new_videos(self) -> list[PlaylistVideo]:
        return [video for video in self._videos if self.status_of(video) == STATUS_NEW]

    def as_dict(self) -> dict:
        return {"videos": [{**video.as_dict(), "status": self.status_of(video)} for video in self._videos],
                "new": len(self.new_videos())}
