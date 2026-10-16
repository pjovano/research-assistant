from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _port_fakes import FakeTranscriber
from _ports.compute import Segment, Transcriber
from _rag_fakes import temp_directory

SEGMENTS = [Segment(0, 2400, "Thank you for coming."), Segment(2400, 6100, "Today I speak about Hegel.")]
LANGUAGE = "en"


class TranscriberContract:
    def transcriber(self) -> Transcriber:
        raise NotImplementedError

    def setUp(self) -> None:
        self.audio = temp_directory(self) / "talk.wav"
        self.audio.write_bytes(b"")

    def transcribed(self) -> list[Segment]:
        return self.transcriber().segments(self.audio, LANGUAGE)

    def test_every_segment_is_a_segment_of_the_port(self) -> None:
        self.assertTrue(all(isinstance(segment, Segment) for segment in self.transcribed()))

    def test_every_segment_ends_no_earlier_than_it_starts(self) -> None:
        self.assertTrue(all(0 <= segment.start_ms <= segment.end_ms for segment in self.transcribed()))

    def test_the_segments_come_in_the_order_they_were_spoken(self) -> None:
        starts = [segment.start_ms for segment in self.transcribed()]
        self.assertEqual(sorted(starts), starts)

    def test_an_unnamed_language_is_accepted(self) -> None:
        self.assertIsInstance(self.transcriber().segments(self.audio, None), list)


class TestFakeTranscriberKeepsTheContract(TranscriberContract, unittest.TestCase):
    def transcriber(self) -> Transcriber:
        return FakeTranscriber(SEGMENTS)


if __name__ == "__main__":
    unittest.main()
