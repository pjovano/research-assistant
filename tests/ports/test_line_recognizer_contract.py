from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _port_fakes import FakeLineRecognizer
from _ports.compute import LineRecognizer

IMAGES = ("first line", "second line", "third line")


class LineRecognizerContract:
    def recognizer(self) -> LineRecognizer:
        raise NotImplementedError

    def images(self) -> list:
        raise NotImplementedError

    def test_each_image_gets_one_text_in_order(self) -> None:
        images = self.images()
        texts = self.recognizer().read(images)
        self.assertEqual(len(images), len(texts))
        self.assertTrue(all(isinstance(text, str) for text in texts))

    def test_no_image_reads_as_no_text(self) -> None:
        self.assertEqual([], self.recognizer().read([]))


class TestFakeLineRecognizerKeepsTheContract(LineRecognizerContract, unittest.TestCase):
    def recognizer(self) -> LineRecognizer:
        return FakeLineRecognizer({image: image for image in IMAGES})

    def images(self) -> list:
        return list(IMAGES)

    def test_the_fake_reads_each_image_as_its_text(self) -> None:
        self.assertEqual(list(IMAGES), self.recognizer().read(self.images()))


if __name__ == "__main__":
    unittest.main()
