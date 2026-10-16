from __future__ import annotations

from .commands import Subprocess
from .settings import TalkSettings
from .talk import TalkEntry, Talks, talks_dir

AUDIO_ARGUMENTS = ("-x", "--audio-format", "wav", "--postprocessor-args", "ffmpeg:-ar 16000 -ac 1",
                   "--write-info-json", "--no-overwrites", "--ignore-errors")
OUTPUT_TEMPLATE = "%(id)s/audio.%(ext)s"


class AudioFetch:
    def __init__(self, urls: list[str], settings: TalkSettings, runner: Subprocess) -> None:
        self._urls = urls
        self._settings = settings
        self._runner = runner

    def run(self) -> list[TalkEntry]:
        fetched_before = {entry.video_id for entry in Talks.all()}
        talks_dir().mkdir(parents=True, exist_ok=True)
        self._runner.run(self.command())
        return [entry for entry in Talks.all() if entry.video_id not in fetched_before]

    def command(self) -> list[str]:
        template = str(talks_dir() / OUTPUT_TEMPLATE)
        return [self._settings.yt_dlp, *AUDIO_ARGUMENTS, "-o", template, *self._urls]
