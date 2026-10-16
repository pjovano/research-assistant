from __future__ import annotations

import sys
from pathlib import Path


def _lib_dir() -> Path:
    here = Path(__file__).resolve()
    return next(parent / "lib" for parent in here.parents if (parent / "lib" / "vault.py").is_file())


sys.path.insert(0, str(_lib_dir()))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _transcribe.checking import MIN_KEPT_RATIO, REQUIRED_CARD_FIELDS, VERDICT_FAILED, VERDICT_PASSED, ReviewCheck
from _transcribe.cli import CommandLine, Commands, main
from _transcribe.commands import Subprocess, ToolFailed
from _transcribe.diarizing import (
    DiarizationUnavailable,
    PyannotePipeline,
    SpeakerTurns,
    Turn,
    TurnsFile,
    WaveformFile,
)
from _transcribe.fetching import AudioFetch
from _transcribe.filing import (
    FilingRefused,
    TalkFiling,
    TalkRecord,
    TranscriptCitekey,
    ZoteroLink,
    recording_url_of,
)
from _transcribe.listing import LOOP_REPEATS, MAX_PART_WORDS, LoopedSentences, Part, ReviewListing, TranscriptParts
from _transcribe.mending import MarkerMend
from _transcribe.merging import MAX_UTTERANCE_WORDS, UNKNOWN_SPEAKER, SpeakerAssignment, Utterance, ends_sentence
from _transcribe.playlist import (
    STATUS_HELD,
    STATUS_IN_PROGRESS,
    STATUS_NEW,
    HeldTalks,
    PlaylistListing,
    PlaylistReport,
    PlaylistVideo,
    video_id_of,
)
from _transcribe.raw import Paragraph, RawTranscript, TranscriptText, timestamp
from _transcribe.settings import TalkSettings
from _transcribe.talk import (
    STAGE_ABSENT,
    STAGE_FETCHED,
    STAGE_REVIEWED,
    STAGE_TRANSCRIBED,
    Recording,
    TalkEntry,
    Talks,
    talks_dir,
)
from _transcribe.whispering import Segment, SegmentsFile, TranscriptionPrompt, WhisperOutput, WhisperRun

__all__ = [
    "LOOP_REPEATS", "LoopedSentences", "MarkerMend", "ends_sentence", "MAX_PART_WORDS", "MAX_UTTERANCE_WORDS",
    "MIN_KEPT_RATIO", "REQUIRED_CARD_FIELDS", "STAGE_ABSENT", "STAGE_FETCHED",
    "STAGE_REVIEWED", "STATUS_HELD", "STATUS_IN_PROGRESS", "STATUS_NEW", "HeldTalks", "PlaylistListing",
    "PlaylistReport", "PlaylistVideo", "video_id_of",
    "STAGE_TRANSCRIBED", "UNKNOWN_SPEAKER", "VERDICT_FAILED", "VERDICT_PASSED", "AudioFetch", "CommandLine",
    "Commands", "DiarizationUnavailable", "FilingRefused", "Paragraph", "Part", "PyannotePipeline", "RawTranscript",
    "Recording", "ReviewCheck", "ReviewListing", "Segment", "SegmentsFile", "SpeakerAssignment", "SpeakerTurns",
    "Subprocess", "TalkEntry", "TalkFiling", "TalkRecord", "TalkSettings", "Talks", "ToolFailed",
    "TranscriptCitekey", "TranscriptParts", "TranscriptText", "TranscriptionPrompt", "Turn", "TurnsFile",
    "Utterance", "WaveformFile", "WhisperOutput", "WhisperRun", "ZoteroLink", "main", "recording_url_of", "talks_dir",
    "timestamp",
]


if __name__ == "__main__":
    main()
