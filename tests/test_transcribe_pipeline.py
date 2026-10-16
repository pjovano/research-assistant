from __future__ import annotations

import json
import unittest
import wave
from pathlib import Path
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import transcribe
from _transcribe_fixtures import (
    CARD,
    INFO,
    RAW_TEXT,
    RECORDING_URL,
    REVIEWED_TEXT,
    TURNS,
    VIDEO_ID,
    WHISPER_JSON,
    RecordedRunner,
    Review,
    TalkTestCase,
)

SEGMENTS = transcribe.WhisperOutput.segments(WHISPER_JSON)
SETTINGS = transcribe.TalkSettings({"whisper_model": "~/models/ggml-large-v3-turbo.bin"})


class TestRecording(TalkTestCase):
    def test_the_upload_date_is_read_as_an_iso_date_and_a_year(self) -> None:
        recording = self.fetched().recording()
        self.assertEqual(("2019-03-14", 2019), (recording.upload_date, recording.year))

    def test_a_missing_upload_date_leaves_no_year(self) -> None:
        recording = self.fetched(upload_date="").recording()
        self.assertEqual(("", None), (recording.upload_date, recording.year))

    def test_the_chapters_carry_their_titles_and_start_seconds(self) -> None:
        self.assertEqual({"title": "Q&A", "start_seconds": 2400}, self.fetched().recording().chapters[1])


class TestTalkStages(TalkTestCase):
    def test_a_talk_with_an_audio_record_is_fetched(self) -> None:
        self.assertEqual(transcribe.STAGE_FETCHED, self.fetched().stage())

    def test_a_talk_with_a_raw_transcript_is_transcribed(self) -> None:
        self.assertEqual(transcribe.STAGE_TRANSCRIBED, self.transcribed().stage())

    def test_a_talk_with_a_card_is_reviewed(self) -> None:
        self.assertEqual(transcribe.STAGE_REVIEWED, self.reviewed().stage())

    def test_an_unfetched_id_is_unknown(self) -> None:
        with self.assertRaises(LookupError):
            transcribe.Talks.named("nothing")

    def test_every_fetched_talk_is_listed_in_id_order(self) -> None:
        self.fetched("b"), self.fetched("a")
        self.assertEqual(["a", "b"], [entry.video_id for entry in transcribe.Talks.all()])


class TestAudioFetch(TalkTestCase):
    def test_the_command_downloads_sixteen_kilohertz_mono_wav_with_the_record(self) -> None:
        command = transcribe.AudioFetch([RECORDING_URL], SETTINGS, RecordedRunner()).command()
        self.assertEqual("yt-dlp", command[0])
        self.assertIn("ffmpeg:-ar 16000 -ac 1", command)
        self.assertIn("--write-info-json", command)
        self.assertEqual(RECORDING_URL, command[-1])

    def test_the_output_template_puts_each_talk_in_its_own_directory_under_talks(self) -> None:
        command = transcribe.AudioFetch([RECORDING_URL], SETTINGS, RecordedRunner()).command()
        template = command[command.index("-o") + 1]
        self.assertTrue(template.startswith(str(transcribe.talks_dir())))
        self.assertTrue(template.endswith("%(id)s/audio.%(ext)s"))

    def test_only_the_talks_the_run_added_are_reported(self) -> None:
        self.fetched("old")
        runner = RecordedRunner(on_run=lambda _arguments: self.fetched("new"))
        fetched = transcribe.AudioFetch([RECORDING_URL], SETTINGS, runner).run()
        self.assertEqual(["new"], [entry.video_id for entry in fetched])


class TestWhisperOutput(unittest.TestCase):
    def test_segments_carry_millisecond_offsets_and_stripped_text(self) -> None:
        self.assertEqual(transcribe.Segment(0, 4000, "Thank you for the introduction."), SEGMENTS[0])

    def test_a_blank_segment_is_dropped(self) -> None:
        self.assertEqual(3, len(SEGMENTS))


class TestTranscriptionPrompt(TalkTestCase):
    def test_the_prompt_carries_the_title_the_channel_and_the_description_without_links(self) -> None:
        prompt = transcribe.TranscriptionPrompt(self.fetched().recording()).text()
        self.assertIn("Robert Pippin", prompt)
        self.assertIn("Philosophy Talks", prompt)
        self.assertNotIn("https://", prompt)

    def test_a_title_opening_with_a_name_label_reaches_the_prompt_without_the_colon(self) -> None:
        recording = self.fetched(title="Robert Pippin: Hegel on Logic").recording()
        prompt = transcribe.TranscriptionPrompt(recording).text()
        self.assertTrue(prompt.startswith("Robert Pippin, Hegel on Logic."))
        self.assertNotIn(":", prompt)


class TestWhisperRun(TalkTestCase):
    def _run(self, settings: transcribe.TalkSettings, language: str | None = None) -> list[transcribe.Segment]:
        entry = self.fetched()
        model = self.vault.named("model.bin")
        model.write_bytes(b"ggml")
        values = {"whisper_model": str(model)}
        runner = RecordedRunner(on_run=lambda arguments: self._write_output(arguments))
        self.runner = runner
        return transcribe.WhisperRun(entry, transcribe.TalkSettings(values), runner).run(language)

    @staticmethod
    def _write_output(arguments: list[str]) -> None:
        prefix = arguments[arguments.index("-of") + 1]
        with open(f"{prefix}.json", "w", encoding="utf-8") as output:
            json.dump(WHISPER_JSON, output)

    def test_the_run_writes_the_segments_file_and_returns_the_segments(self) -> None:
        segments = self._run(SETTINGS)
        self.assertEqual(segments, transcribe.SegmentsFile(transcribe.TalkEntry(VIDEO_ID).segments).read())

    def test_the_language_defaults_to_detection(self) -> None:
        self._run(SETTINGS)
        [command] = self.runner.commands
        self.assertEqual("auto", command[command.index("-l") + 1])

    def test_a_named_language_is_passed_through(self) -> None:
        self._run(SETTINGS, "de")
        [command] = self.runner.commands
        self.assertEqual("de", command[command.index("-l") + 1])

    def test_a_missing_model_setting_fails_before_the_tool_runs(self) -> None:
        entry = self.fetched()
        with self.assertRaises(transcribe.ToolFailed):
            transcribe.WhisperRun(entry, transcribe.TalkSettings({}), RecordedRunner()).command()


class TestWaveformFile(TalkTestCase):
    def _wav(self, channels: int = 1, width: int = 2, frames: bytes = b"\x00\x00\xff\x7f\x00\x80") -> Path:
        path = self.vault.named("tone.wav")
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(channels)
            audio.setsampwidth(width)
            audio.setframerate(16000)
            audio.writeframes(frames)
        return path

    def test_the_input_carries_the_samples_as_one_channel_of_floats_and_the_rate(self) -> None:
        given = transcribe.WaveformFile(self._wav()).as_input()
        self.assertEqual((1, 3), tuple(given["waveform"].shape))
        self.assertEqual(16000, given["sample_rate"])
        self.assertAlmostEqual(-1.0, float(given["waveform"][0, 2]))

    def test_a_stereo_file_is_refused(self) -> None:
        with self.assertRaises(transcribe.DiarizationUnavailable):
            transcribe.WaveformFile(self._wav(channels=2, frames=b"\x00\x00\x00\x00")).as_input()


class FailingPipeline:
    def __call__(self, waveform: dict):
        raise RuntimeError("out of memory")

    def to(self, device):
        return self


class TestPyannotePipelineFailures(TalkTestCase):
    def test_an_error_during_inference_is_reported_as_unavailable(self) -> None:
        pipeline = transcribe.PyannotePipeline("a-model")
        with mock.patch.object(pipeline, "_loaded", return_value=FailingPipeline()):
            with self.assertRaises(transcribe.DiarizationUnavailable) as raised:
                pipeline.turns(self.fetched_wav())
        self.assertIn("out of memory", str(raised.exception))

    def fetched_wav(self) -> Path:
        path = self.vault.named("tone.wav")
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\x00\x00")
        return path


class TestSpeakerAssignment(unittest.TestCase):
    def test_a_segment_takes_the_speaker_of_the_turn_it_overlaps_most(self) -> None:
        utterances = transcribe.SpeakerAssignment(SEGMENTS, TURNS).utterances()
        self.assertEqual(["SPEAKER_00", "SPEAKER_01"], [utterance.speaker for utterance in utterances])

    def test_consecutive_segments_of_one_speaker_merge_into_one_utterance(self) -> None:
        [first, _second] = transcribe.SpeakerAssignment(SEGMENTS, TURNS).utterances()
        self.assertEqual("Thank you for the introduction. Logic, for Hegel, is metaphysics.", first.text)

    def test_an_utterance_starts_where_its_first_segment_starts(self) -> None:
        [_first, second] = transcribe.SpeakerAssignment(SEGMENTS, TURNS).utterances()
        self.assertEqual(2400000, second.start_ms)

    def test_a_segment_between_turns_takes_the_nearest_turn(self) -> None:
        gap = [transcribe.Segment(11000, 12000, "Between.")]
        [utterance] = transcribe.SpeakerAssignment(gap, TURNS).utterances()
        self.assertEqual("SPEAKER_00", utterance.speaker)

    def test_one_speaker_running_past_the_word_limit_opens_a_new_utterance_at_a_sentence_start(self) -> None:
        long_run = [transcribe.Segment(number * 1000, number * 1000 + 900, "word " * 59 + "end.")
                    for number in range(9)]
        one_turn = [transcribe.Turn(0, 10000, "SPEAKER_00")]
        utterances = transcribe.SpeakerAssignment(long_run, one_turn).utterances()
        self.assertEqual([0, 5000], [utterance.start_ms for utterance in utterances])
        self.assertTrue(all(len(u.text.split()) <= transcribe.MAX_UTTERANCE_WORDS + 60 for u in utterances))

    def test_an_utterance_past_the_word_limit_closes_only_at_a_sentence_end(self) -> None:
        run = [transcribe.Segment(0, 900, "word " * 250 + "and the sentence"),
               transcribe.Segment(1000, 1900, "ends here."),
               transcribe.Segment(2000, 2900, "A new sentence.")]
        utterances = transcribe.SpeakerAssignment(run, [transcribe.Turn(0, 3000, "SPEAKER_00")]).utterances()
        self.assertEqual([0, 2000], [utterance.start_ms for utterance in utterances])
        self.assertTrue(utterances[0].text.endswith("ends here."))

    def test_with_no_turns_every_segment_is_unknown(self) -> None:
        utterances = transcribe.SpeakerAssignment(SEGMENTS, []).utterances()
        self.assertEqual({transcribe.UNKNOWN_SPEAKER}, {utterance.speaker for utterance in utterances})


class TestTranscriptText(unittest.TestCase):
    def test_milliseconds_render_as_hours_minutes_seconds(self) -> None:
        self.assertEqual("01:02:03", transcribe.timestamp(3723999))

    def test_utterances_render_with_a_time_marker_and_a_bold_speaker(self) -> None:
        utterances = transcribe.SpeakerAssignment(SEGMENTS, TURNS).utterances()
        self.assertEqual(RAW_TEXT, transcribe.TranscriptText.rendered(utterances))

    def test_paragraphs_parse_back_with_their_times_and_speakers(self) -> None:
        paragraphs = transcribe.TranscriptText.paragraphs(RAW_TEXT)
        self.assertEqual([("00:00:00", "SPEAKER_00"), ("00:40:00", "SPEAKER_01")],
                         [(paragraph.time, paragraph.speaker) for paragraph in paragraphs])

    def test_a_heading_paragraph_has_no_time_and_no_speaker(self) -> None:
        [heading] = transcribe.TranscriptText.paragraphs("## Talk\n")
        self.assertEqual((None, None, "## Talk"), (heading.time, heading.speaker, heading.text))


class TestTranscriptParts(unittest.TestCase):
    PARAGRAPHS = [transcribe.Paragraph(f"00:00:0{number}", f"**A:** {'word ' * 10}") for number in range(5)]

    def test_paragraphs_fill_a_part_up_to_the_word_limit(self) -> None:
        parts = transcribe.TranscriptParts(self.PARAGRAPHS, max_words=25).parts()
        self.assertEqual([2, 2, 1], [len(part.paragraphs) for part in parts])

    def test_a_part_names_its_markers_in_order(self) -> None:
        [first, *_rest] = transcribe.TranscriptParts(self.PARAGRAPHS, max_words=25).parts()
        self.assertEqual(["00:00:00", "00:00:01"], first.markers)

    def test_a_part_renders_its_paragraphs_with_their_markers(self) -> None:
        [part] = transcribe.TranscriptParts(transcribe.TranscriptText.paragraphs(RAW_TEXT)).parts()
        self.assertEqual(RAW_TEXT.strip(), part.text())


class TestReviewListing(TalkTestCase):
    def test_the_listing_names_the_recording_the_parts_and_the_card(self) -> None:
        entry = self.transcribed()
        listing = json.loads(transcribe.ReviewListing(entry).write().read_text(encoding="utf-8"))
        self.assertEqual(INFO["title"], listing["recording"]["title"])
        self.assertEqual(str(entry.card), listing["card"])
        [part] = listing["parts"]
        self.assertEqual((1, str(entry.part_path(1)), ["SPEAKER_00", "SPEAKER_01"]),
                         (part["number"], part["reviewed_path"], part["speakers"]))

    def test_the_listing_creates_the_reviewed_directory(self) -> None:
        entry = self.transcribed()
        transcribe.ReviewListing(entry).write()
        self.assertTrue(entry.reviewed_dir.is_dir())


class TestLoopedSentences(unittest.TestCase):
    def test_a_sentence_repeated_three_times_or_more_counts_once(self) -> None:
        text = "**A:** Real words here. " + "Looped phrase again. " * 50 + "**B:** More real words."
        self.assertEqual(9, transcribe.LoopedSentences(text).heard_words())

    def test_a_loop_interleaved_across_speakers_still_counts_once(self) -> None:
        text = "**A:** Looped phrase again. Looped phrase again.\n\n**B:** No. Looped phrase again."
        self.assertEqual(4, transcribe.LoopedSentences(text).heard_words())

    def test_a_sentence_said_twice_counts_twice(self) -> None:
        self.assertEqual(6, transcribe.LoopedSentences("Say it twice. Say it twice.").heard_words())


class TestMarkerMend(unittest.TestCase):
    def mended(self, body: str) -> str:
        return transcribe.MarkerMend(body).mended()

    def test_a_fragment_cut_by_a_marker_moves_back_to_its_sentence(self) -> None:
        body = "%% 00:00:01 %%\n**A:** The sentence runs\n\n%% 00:00:09 %%\n**A:** on past the marker. Next one."
        self.assertEqual("%% 00:00:01 %%\n**A:** The sentence runs on past the marker.\n\n"
                         "%% 00:00:09 %%\n**A:** Next one.", self.mended(body))

    def test_a_paragraph_that_is_all_fragment_joins_the_one_before_and_its_marker_goes(self) -> None:
        body = "%% 00:00:01 %%\n**A:** The sentence runs\n\n%% 00:00:09 %%\n**A:** on and ends."
        self.assertEqual("%% 00:00:01 %%\n**A:** The sentence runs on and ends.", self.mended(body))

    def test_a_speaker_cutting_in_keeps_the_marker(self) -> None:
        body = "%% 00:00:01 %%\n**A:** I was saying that\n\n%% 00:00:04 %%\n**B:** Sorry, may I ask?"
        self.assertEqual(body, self.mended(body))

    def test_a_heading_between_paragraphs_is_left_alone(self) -> None:
        body = "%% 00:00:01 %%\n**A:** Thanks\n\n## Discussion\n\n%% 00:00:04 %%\n**A:** first question."
        self.assertEqual(body, self.mended(body))

    def test_a_marker_opening_a_sentence_is_left_alone(self) -> None:
        body = "%% 00:00:01 %%\n**A:** One sentence.\n\n%% 00:00:04 %%\n**A:** Another."
        self.assertEqual(body, self.mended(body))


class TestReviewCheck(TalkTestCase):
    def test_a_complete_review_passes(self) -> None:
        self.assertEqual(transcribe.VERDICT_PASSED, transcribe.ReviewCheck(self.reviewed()).report()["verdict"])

    def test_a_missing_part_fails(self) -> None:
        entry = self.reviewed(review=Review(parts=()))
        self.assertIn("part 1 missing", " ".join(transcribe.ReviewCheck(entry).report()["problems"]))

    def test_a_time_marker_the_raw_transcript_lacks_fails(self) -> None:
        invented = "## Talk\n\n%% 00:00:00 %%\n**Pippin:** Logic.\n\n%% 00:41:00 %%\n**Pippin:** More.\n"
        problems = transcribe.ReviewCheck(self.reviewed(review=Review(parts=(invented,)))).report()["problems"]
        self.assertIn("00:41:00", " ".join(problems))

    def test_a_review_that_drops_a_hallucinated_loop_passes_the_word_floor(self) -> None:
        looped = RAW_TEXT.replace("Logic, for Hegel, is metaphysics.",
                                  "Logic, for Hegel, is metaphysics. " + "It is not a way of saying that. " * 40)
        entry = self.transcribed(raw=looped)
        entry.reviewed_dir.mkdir()
        entry.part_path(1).write_text(REVIEWED_TEXT, encoding="utf-8")
        entry.card.write_text(json.dumps(CARD), encoding="utf-8")
        self.assertEqual([], transcribe.ReviewCheck(entry).report()["problems"])

    def test_a_part_that_dropped_most_of_the_words_fails(self) -> None:
        entry = self.reviewed(review=Review(parts=("## Talk\n\n**Pippin:** Logic.\n",)))
        problems = transcribe.ReviewCheck(entry).report()["problems"]
        self.assertIn("keeps", " ".join(problems))

    def test_a_machine_speaker_label_left_in_place_fails(self) -> None:
        unresolved = "## Talk\n\n" + RAW_TEXT
        problems = transcribe.ReviewCheck(self.reviewed(review=Review(parts=(unresolved,)))).report()["problems"]
        self.assertIn("SPEAKER_00", " ".join(problems))

    def test_a_review_with_no_heading_fails(self) -> None:
        unheaded = RAW_TEXT.replace("SPEAKER_00", "Pippin").replace("SPEAKER_01", "Audience member")
        problems = transcribe.ReviewCheck(self.reviewed(review=Review(parts=(unheaded,)))).report()["problems"]
        self.assertIn("heading", " ".join(problems))

    def test_a_part_file_the_listing_does_not_name_fails(self) -> None:
        entry = self.reviewed(review=Review(parts=(REVIEWED_TEXT, REVIEWED_TEXT)))
        problems = transcribe.ReviewCheck(entry).report()["problems"]
        self.assertIn(str(entry.part_path(2)), " ".join(problems))

    def test_a_card_lacking_a_required_field_fails(self) -> None:
        card = {"title": "T", "presenters": [{"lastName": "Pippin"}], "year": 2019, "meeting": None}
        problems = transcribe.ReviewCheck(self.reviewed(review=Review(card=card))).report()["problems"]
        self.assertEqual(["card lacks dropped"], problems)

    def test_a_card_whose_presenter_lacks_a_surname_fails(self) -> None:
        card = {"title": "T", "presenters": [{"firstName": "Robert"}], "year": 2019, "meeting": None, "dropped": ""}
        problems = transcribe.ReviewCheck(self.reviewed(review=Review(card=card))).report()["problems"]
        self.assertEqual(["presenter 1 lacks a lastName"], problems)

    def test_a_card_whose_year_is_text_fails(self) -> None:
        card = {"title": "T", "presenters": [{"lastName": "Pippin"}], "year": "2019", "meeting": None, "dropped": ""}
        problems = transcribe.ReviewCheck(self.reviewed(review=Review(card=card))).report()["problems"]
        self.assertEqual(["card year is not an integer"], problems)


if __name__ == "__main__":
    unittest.main()
