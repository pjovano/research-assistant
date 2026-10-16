from __future__ import annotations

import json
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

from .talk import TalkEntry

MILLISECONDS_PER_SECOND = 1000
MONO_CHANNELS = 1
INT16_BYTES = 2
INT16_FULL_SCALE = 32768.0
GPU_DEVICE = "mps"
CPU_DEVICE = "cpu"
_ENCODING = "utf-8"
_NOT_INSTALLED = ("pyannote.audio is not installed in the vault's environment; rebuild the environment "
                  "from requirements.lock")
_NOT_LOADED = ("the diarization model {model} did not load: {cause}. Download it once from a terminal with "
               "HF_HUB_OFFLINE unset, after accepting its terms on Hugging Face")


@dataclass(frozen=True)
class Turn:
    start_ms: int
    end_ms: int
    speaker: str


class DiarizationUnavailable(RuntimeError):
    pass


class TurnsFile:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, turns: list[Turn]) -> None:
        self._path.write_text(json.dumps([asdict(turn) for turn in turns], indent=1), encoding=_ENCODING)

    def read(self) -> list[Turn]:
        return [Turn(**entry) for entry in json.loads(self._path.read_text(encoding=_ENCODING))]


class WaveformFile:
    def __init__(self, path: Path) -> None:
        self._path = path

    def as_input(self) -> dict:
        import numpy
        import torch
        with wave.open(str(self._path), "rb") as audio:
            self._require_mono_16_bit(audio)
            frames = audio.readframes(audio.getnframes())
            sample_rate = audio.getframerate()
        samples = numpy.frombuffer(frames, dtype=numpy.int16).astype(numpy.float32) / INT16_FULL_SCALE
        return {"waveform": torch.from_numpy(samples).unsqueeze(0), "sample_rate": sample_rate}

    def _require_mono_16_bit(self, audio) -> None:
        if audio.getnchannels() != MONO_CHANNELS or audio.getsampwidth() != INT16_BYTES:
            raise DiarizationUnavailable(f"{self._path} is not 16-bit mono WAV; fetch writes 16 kHz mono")


class PyannotePipeline:
    def __init__(self, model_name: str) -> None:
        self._model_name = model_name

    def turns(self, audio: Path) -> list[Turn]:
        annotation = self._annotation_of(self._diarized(self._loaded(), WaveformFile(audio).as_input()))
        return [Turn(_milliseconds(segment.start), _milliseconds(segment.end), str(label))
                for segment, _track, label in annotation.itertracks(yield_label=True)]

    def _diarized(self, pipeline, waveform: dict):
        try:
            return pipeline(waveform)
        except Exception as error:
            raise DiarizationUnavailable(f"the diarization model {self._model_name} failed on the audio: {error}") \
                from error

    def _loaded(self):
        pipeline_class = self._pipeline_class()
        try:
            pipeline = pipeline_class.from_pretrained(self._model_name)
        except Exception as error:
            raise DiarizationUnavailable(_NOT_LOADED.format(model=self._model_name, cause=error)) from error
        if pipeline is None:
            raise DiarizationUnavailable(_NOT_LOADED.format(model=self._model_name, cause="not in the cache"))
        return pipeline.to(self._device())

    @staticmethod
    def _pipeline_class():
        try:
            from pyannote.audio import Pipeline
        except ImportError as error:
            raise DiarizationUnavailable(_NOT_INSTALLED) from error
        return Pipeline

    @staticmethod
    def _device():
        import torch
        return torch.device(GPU_DEVICE if torch.backends.mps.is_available() else CPU_DEVICE)

    @staticmethod
    def _annotation_of(output):
        exclusive = getattr(output, "exclusive_speaker_diarization", None)
        return exclusive if exclusive is not None else getattr(output, "speaker_diarization", output)


def _milliseconds(seconds: float) -> int:
    return int(round(seconds * MILLISECONDS_PER_SECOND))


class SpeakerTurns:
    def __init__(self, entry: TalkEntry, pipeline: PyannotePipeline) -> None:
        self._entry = entry
        self._pipeline = pipeline

    def run(self) -> list[Turn]:
        turns = self._pipeline.turns(self._entry.audio)
        TurnsFile(self._entry.turns).write(turns)
        return turns
