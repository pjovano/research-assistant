---
name: transcribe-talks
description: "Transcribe — on the recording URLs the user gives, fetch each talk's audio, transcribe it with its speakers, have the transcript reviewer make it readable, file it as a transcript with its Zotero record, and delete the audio; then Stage 4 places each transcript and Stage 6 indexes it."
allowed-tools: Read, Agent, Bash(~/.research-vault/venv/bin/python .claude/skills/transcribe-talks/scripts/transcribe.py:*), Bash(~/.research-vault/venv/bin/python .claude/skills/classify-and-place/scripts/bibliographies.py:*)
---

# transcribe-talks (run on the user's URLs; the transcript reviewer reviews)

**A talk is one recorded talk, identified by its recording's URL.** A
recording is the video the URL names. A transcript is one note of
`research vault/corpus/talk transcripts/`, `<basename>.md`: the frontmatter `file`
writes and Stage 4 classifies, and the body the transcript reviewer wrote,
the talk's words with a time marker where each utterance begins. A time
marker is the Obsidian comment `%% hh:mm:ss %%` naming the second of the
recording an utterance begins at; Obsidian's Reading view hides it.

**A transcript is paraphrased, never quoted.** The `answer-questions` skill states
how a transcript is cited.

**The audio is never kept.** `transcribe` deletes the audio once the raw
transcript is written; the vault holds the transcript and the Zotero record,
and the recording stays at its URL.

**A talk batch is the URLs the user gives in one message, or the new talks
of the playlist when the user asks for a check of it.** The batch rules
of `CLAUDE.md` §4 bind a talk batch: NEVER end a turn while a talk of the
batch has a step left; a talk whose step reaches `set the talk aside` keeps
its scratch entry as it is and its question for the one report; a failure
that would recur on every talk stops the batch.

## Setup, once per machine

| Tool | Install | `machine.json` key |
| --- | --- | --- |
| `yt-dlp` and `ffmpeg` | `brew install yt-dlp ffmpeg` | `yt_dlp`, when the binary is not `yt-dlp` on `PATH`; `talks_playlist`, the URL of the playlist the user keeps, on each machine |
| whisper.cpp | `brew install whisper-cpp`, then download `ggml-large-v3-turbo.bin` from the `ggerganov/whisper.cpp` repository on Hugging Face into `~/.research-vault/models/` | `whisper_model`, the model file's path, required; `whisper_cli`, when the binary is not `whisper-cli` on `PATH` |
| pyannote.audio | pinned in `requirements.lock`; accept the terms of `pyannote/speaker-diarization-community-1` on Hugging Face, run `hf auth login`, then download the model once from a terminal with `HF_HUB_OFFLINE` unset: `~/.research-vault/venv/bin/python -c "from pyannote.audio import Pipeline; Pipeline.from_pretrained('pyannote/speaker-diarization-community-1')"` | `diarization_model`, when another model is wanted |

If `transcribe` exits 1 naming a missing tool, a missing `whisper_model`, or
a diarization model that did not load, stop and ask the user to run the
setup row named: the failure recurs on every talk.

## The playlist

**The playlist is the YouTube playlist `machine.json` names under
`talks_playlist`, which the user keeps.** A video on it is `held` if a
transcript's `url:` names it, `in progress` if a talk entry carries its id,
and `new` otherwise; a held or in-progress video is never fetched again.

| Command | Does |
| --- | --- |
| `playlist` | read-only; every video of the playlist with its title, its duration, and its status, and the count of new videos |
| `fetch --playlist` | fetches the new videos, as `fetch` fetches URLs; prints `the playlist holds no new talk` when none is new |

If the user asks for a check of the playlist, run `playlist`, then `fetch
--playlist`, then step 2 onward on every talk fetched. If `playlist` exits 1
naming no `talks_playlist`, stop and ask the user for the playlist's URL. If
the playlist holds no new talk, report that and stop.

## The talk entry

**A talk entry is `~/.research-vault/cache/talks/<video id>/`**, the scratch
entry one talk passes through. `sweep` never deletes `talks/`; `file --apply`
deletes the entry it files, and reports `entry_deleted: false` with
`entry_error` when it cannot.

| File | Written by | Holds |
| --- | --- | --- |
| `audio.wav` | `fetch` | the recording's audio, 16 kHz mono; deleted by `transcribe` |
| `audio.info.json` | `fetch` | the recording's record: title, channel, upload date, description, chapters, URL |
| `segments.json`, `turns.json` | `transcribe` | whisper.cpp's timed segments; pyannote's speaker turns |
| `raw.md` | `transcribe` | the raw transcript: one paragraph per utterance, a time marker, then `**<speaker label>:** <text>` |
| `listing.json` | `review-listing` | the talk listing the transcript reviewer reads |
| `reviewed/part-NN.md` | the transcript reviewer | the reviewed transcript, one file per part of the listing |
| `card.json` | the transcript reviewer | the talk card: `title`, `presenters`, `year`, `meeting`, `dropped` |
| `zotero-item.json` | `file --apply` | the Zotero record's item key and citekey, written once the record is saved; a re-run reuses them |

## Procedure

Every command is
`~/.research-vault/venv/bin/python .claude/skills/transcribe-talks/scripts/transcribe.py <subcommand>`.
Every command prints JSON; a failure prints `{"error": ...}` and exits 1.

1. **Fetch.** Run `fetch <url> [<url>...]` once for the batch. A playlist
   URL fetches every talk in it. The output lists each talk fetched with its
   `video_id`, its title, its channel, and its duration. If `fetch` exits 1,
   run `status`: every talk `status` lists at stage `fetched` is fetched;
   report the error for the rest, and carry the fetched talks on.
2. **Transcribe, one talk at a time.** Run `transcribe <video_id>`, with
   `--language <code>` if the user named the talk's language. NEVER run two
   `transcribe` commands at once: the whisper run takes the GPU whole. The
   output names the segments, the speaker turns, the speakers, and the raw
   transcript. If `transcribe` exits 1 for one talk with any other error,
   set the talk aside.
3. **List.** Run `review-listing <video_id>`. The output names the talk
   listing's path, its parts, and its words. If `review-listing` exits 1,
   set the talk aside, keeping the error as its question.
4. **Review.** Dispatch the `transcript-reviewer` worker: invoke the Agent
   tool with `subagent_type: transcript-reviewer` and `model:
   claude-sonnet-5`, with the path of the talk listing. One dispatch per
   talk.
5. **Check.** Run `review-check <video_id>`. If it exits 1, dispatch the
   worker again once, with the path of the talk listing and the `problems`
   the check printed; if the second check exits 1, set the talk aside,
   keeping the problems as its question.
6. **File.** Run `file <video_id>` and read its plan: the basename, the
   citekey, the Zotero item, and the frontmatter. Then run `file <video_id>
   --apply`: it creates the Zotero record, a `presentation` by its
   presenters under the recording's URL, writes the transcript with the
   frontmatter and the reviewed parts the listing names, in order, and deletes
   the talk entry. `file --apply` runs the check again and refuses a review
   that fails it.

   | `file` error | Do |
   | --- | --- |
   | a note already holds the basename | stop and ask the user: the talk MAY be held already |
   | Zotero is not running | stop the batch and ask the user |
   | Zotero refused the item | set the talk aside |
   | the Zotero item is saved but the note was not written | run `file <video_id> --apply` again: it reuses the item |
   | the review check did not pass | return to step 5 |
   | any other error | set the talk aside, keeping the error as its question |
7. **Classify and place.** Run Stage 4 on the transcript's basename through
   the steps of the `classify-and-place` skill's "The ingest workflow"
   section: `bibliographies.py drive-classify "<basename>"`, a
   `work-classifier` dispatch naming the basename and the `answers` path
   the line prints, then `bibliographies.py drive-classify "<basename>"
   --answers "<answers file>"`. Run the `--answers` calls one talk at a
   time. The work classifier gives a transcript `source_type`
   `transcript`.

   | `state` | Do |
   | --- | --- |
   | `placed` | continue |
   | `aside` | set the talk aside with the line's `question` |
   | `halt` | stop the batch and ask the user the line's `question` |
8. **Check, then index, once per batch.** After the last talk's Stage 4,
   run `bibliographies.py check`, then Stage 6 by the `search` skill. Stage 3 never runs on a transcript, and Stage 5 runs on the transcript's bibliographies at the next batch that touches them: a transcript
   carries no entry list.

**Report once, after the last step.** Name each transcript filed with its
basename and the `dropped` sentence of its talk card, then each set-aside
talk with its question.

## The transcript

| Element | Form |
| --- | --- |
| first line | `[Recording](<url>)`, the link to the recording; the search stores strip it |
| frontmatter | `title`, `author` (the presenters' surnames), `year`, `type: presentation`, `citekey`, `meeting`, then `source_type`, `source_role`, and `field:` for Stage 4; the recording's URL stands on the first line alone |
| headings | `## Talk` opens the talk, `## Discussion` the questions and answers; the transcript reviewer's instructions state the rest |
| paragraph | a time marker on its own line, then `**<Speaker>:** <text>`; a paragraph the reviewer split from another carries no marker; a time marker NEVER falls inside one speaker's sentence: `file` moves the fragment a marker cuts back into the paragraph before it |
| basename | `<FirstCreator> - <Year> - <Title>` by the rule of `CLAUDE.md` §3, the presenters as the creators, the year the talk was given, the talk's main title |

**A transcript is written once, in two parts.** `file` writes the
frontmatter and the body; Stage 4 writes the classification. After Stage 4,
the note changes only on the user's instruction. NEVER run `file --apply`
for a talk whose check did not pass: the check is the review's guarantee.
