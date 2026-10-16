from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .commands import Subprocess, ToolFailed
from .settings import TalkSettings
from .talk import Recording, TalkEntry

AUTO_LANGUAGE = "auto"
OUTPUT_PREFIX_NAME = "whisper"
JSON_SUFFIX = ".json"
MAX_PROMPT_WORDS = 120
LABEL_COLON = ":"
LABEL_REPLACEMENT = ","
_URL_RE = re.compile(r"https?://\S+")
_ENCODING = "utf-8"


@dataclass(frozen=True)
class Segment:
    start_ms: int
    end_ms: int
    text: str


class TranscriptionPrompt:
    def __init__(self, recording: Recording) -> None:
        self._recording = recording

    def text(self) -> str:
        heard = f"{self._recording.title}. {self._recording.channel}. {self._recording.description}"
        words = _URL_RE.sub("", heard).replace(LABEL_COLON, LABEL_REPLACEMENT).split()
        return " ".join(words[:MAX_PROMPT_WORDS])


class WhisperOutput:
    @staticmethod
    def segments(payload: dict) -> list[Segment]:
        return [Segment(int(entry["offsets"]["from"]), int(entry["offsets"]["to"]), str(entry["text"]).strip())
                for entry in payload.get("transcription") or [] if str(entry.get("text", "")).strip()]


class SegmentsFile:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, segments: list[Segment]) -> None:
        self._path.write_text(json.dumps([asdict(segment) for segment in segments], ensure_ascii=False, indent=1),
                              encoding=_ENCODING)

    def read(self) -> list[Segment]:
        return [Segment(**entry) for entry in json.loads(self._path.read_text(encoding=_ENCODING))]


class WhisperRun:
    def __init__(self, entry: TalkEntry, settings: TalkSettings, runner: Subprocess) -> None:
        self._entry = entry
        self._settings = settings
        self._runner = runner

    def run(self, language: str | None = None) -> list[Segment]:
        self._runner.run(self.command(language))
        segments = WhisperOutput.segments(json.loads(self._output_path().read_text(encoding=_ENCODING)))
        SegmentsFile(self._entry.segments).write(segments)
        return segments

    def command(self, language: str | None = None) -> list[str]:
        prompt = TranscriptionPrompt(self._entry.recording()).text()
        return [self._settings.whisper_cli, "-m", str(self._model()), "-f", str(self._entry.audio),
                "-l", language or AUTO_LANGUAGE, "-oj", "-of", str(self._output_prefix()), "-np", "--prompt", prompt]

    def _model(self) -> Path:
        model = self._settings.whisper_model
        if model is None:
            raise ToolFailed("machine.json names no whisper_model; name the path of a whisper.cpp model file")
        if not model.is_file():
            raise ToolFailed(f"whisper_model {model} is not a file")
        return model

    def _output_prefix(self) -> Path:
        return self._entry.directory / OUTPUT_PREFIX_NAME

    def _output_path(self) -> Path:
        return self._output_prefix().with_suffix(JSON_SUFFIX)
