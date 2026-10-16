from __future__ import annotations

import json
import unittest

from _support import LiveTree

LiveTree.activate()

import transcribe
import vault
from _transcribe_fixtures import RecordedRunner, TalkTestCase

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLabc"
SETTINGS = transcribe.TalkSettings({"talks_playlist": PLAYLIST_URL})
LISTING = {"entries": [
    {"id": "held0000001", "title": "A held talk", "duration": 3600},
    {"id": "inprogress1", "title": "A talk in the scratch", "duration": 1800},
    {"id": "brandnew001", "title": "A new talk", "duration": 2400},
    None,
    {"title": "an entry with no id"},
]}


class ListingRunner(RecordedRunner):
    def run(self, arguments: list[str]) -> str:
        super().run(arguments)
        return json.dumps(LISTING)


class TestVideoIds(unittest.TestCase):
    def test_the_id_is_read_from_watch_short_and_embed_urls(self) -> None:
        for url in ("https://www.youtube.com/watch?v=FGUzgcLXNuk&t=1", "https://youtu.be/FGUzgcLXNuk?si=x",
                    "https://www.youtube.com/embed/FGUzgcLXNuk"):
            with self.subTest(url=url):
                self.assertEqual("FGUzgcLXNuk", transcribe.video_id_of(url))

    def test_a_url_naming_no_video_has_no_id(self) -> None:
        self.assertIsNone(transcribe.video_id_of("https://example.org/talk"))


class TestPlaylistListing(unittest.TestCase):
    def test_the_command_dumps_the_flat_playlist_as_json(self) -> None:
        command = transcribe.PlaylistListing(SETTINGS, ListingRunner()).command()
        self.assertEqual(["yt-dlp", "--flat-playlist", "-J", PLAYLIST_URL], command)

    def test_a_missing_playlist_setting_fails_before_the_tool_runs(self) -> None:
        with self.assertRaises(transcribe.ToolFailed):
            transcribe.PlaylistListing(transcribe.TalkSettings({}), ListingRunner()).command()

    def test_entries_without_an_id_are_dropped(self) -> None:
        videos = transcribe.PlaylistListing(SETTINGS, ListingRunner()).videos()
        self.assertEqual(["held0000001", "inprogress1", "brandnew001"], [video.video_id for video in videos])

    def test_a_video_knows_its_watch_url(self) -> None:
        [video, *_rest] = transcribe.PlaylistListing(SETTINGS, ListingRunner()).videos()
        self.assertEqual("https://www.youtube.com/watch?v=held0000001", video.url)


class TestPlaylistReport(TalkTestCase):
    def setUp(self) -> None:
        super().setUp()
        vault.write_frontmatter(vault.TRANSCRIPTS_DIR / "Someone - 2020 - A Held Talk.md", {"title": "A held talk"},
                                "[Recording](https://youtu.be/held0000001)\n\n## Talk\n\nSpoken.\n")
        self.fetched("inprogress1")
        videos = transcribe.PlaylistListing(SETTINGS, ListingRunner()).videos()
        self.report = transcribe.PlaylistReport(videos, transcribe.HeldTalks())

    def test_each_video_is_held_in_progress_or_new(self) -> None:
        statuses = [entry["status"] for entry in self.report.as_dict()["videos"]]
        self.assertEqual([transcribe.STATUS_HELD, transcribe.STATUS_IN_PROGRESS, transcribe.STATUS_NEW], statuses)

    def test_only_the_new_videos_are_fetched(self) -> None:
        self.assertEqual(["brandnew001"], [video.video_id for video in self.report.new_videos()])

    def test_the_report_counts_the_new_videos(self) -> None:
        self.assertEqual(1, self.report.as_dict()["new"])


if __name__ == "__main__":
    unittest.main()
