from __future__ import annotations

from pathlib import Path

import vault

WHISPER_CLI_KEY = "whisper_cli"
WHISPER_MODEL_KEY = "whisper_model"
DIARIZATION_MODEL_KEY = "diarization_model"
YT_DLP_KEY = "yt_dlp"
TALKS_PLAYLIST_KEY = "talks_playlist"

DEFAULT_WHISPER_CLI = "whisper-cli"
DEFAULT_DIARIZATION_MODEL = "pyannote/speaker-diarization-community-1"
DEFAULT_YT_DLP = "yt-dlp"


class TalkSettings:
    def __init__(self, values: dict | None = None) -> None:
        self._values = vault.MACHINE if values is None else values

    @property
    def whisper_cli(self) -> str:
        return self._text(WHISPER_CLI_KEY, DEFAULT_WHISPER_CLI)

    @property
    def whisper_model(self) -> Path | None:
        value = self._values.get(WHISPER_MODEL_KEY)
        return Path(str(value)).expanduser() if value else None

    @property
    def diarization_model(self) -> str:
        return self._text(DIARIZATION_MODEL_KEY, DEFAULT_DIARIZATION_MODEL)

    @property
    def yt_dlp(self) -> str:
        return self._text(YT_DLP_KEY, DEFAULT_YT_DLP)

    @property
    def playlist(self) -> str | None:
        value = self._values.get(TALKS_PLAYLIST_KEY)
        return str(value) if value else None

    def _text(self, key: str, default: str) -> str:
        return str(self._values.get(key) or default)
