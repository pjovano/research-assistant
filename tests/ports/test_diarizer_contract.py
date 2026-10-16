from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _port_fakes import FakeDiarizer
from _ports.compute import Diarizer, Turn
from _rag_fakes import temp_directory

TURNS = [Turn(0, 2400, "SPEAKER_00"), Turn(2400, 6100, "SPEAKER_01")]


class DiarizerContract:
    def diarizer(self) -> Diarizer:
        raise NotImplementedError

    def setUp(self) -> None:
        self.audio = temp_directory(self) / "talk.wav"
        self.audio.write_bytes(b"")

    def test_every_turn_is_a_turn_of_the_port(self) -> None:
        self.assertTrue(all(isinstance(turn, Turn) for turn in self.diarizer().turns(self.audio)))

    def test_every_turn_ends_no_earlier_than_it_starts(self) -> None:
        self.assertTrue(all(0 <= turn.start_ms <= turn.end_ms for turn in self.diarizer().turns(self.audio)))

    def test_every_turn_names_its_speaker(self) -> None:
        self.assertTrue(all(turn.speaker.strip() for turn in self.diarizer().turns(self.audio)))


class TestFakeDiarizerKeepsTheContract(DiarizerContract, unittest.TestCase):
    def diarizer(self) -> Diarizer:
        return FakeDiarizer(TURNS)


if __name__ == "__main__":
    unittest.main()
