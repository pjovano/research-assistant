---
name: extract-corpus
description: "Stage 2 — write a filed PDF's corpus file body from the engine's layout and the text layer, every page through the page checks, and accept the trial they pass; triggered when the corpus file exists and has no body."
allowed-tools: Read, Glob, Bash(~/.research-vault/venv/bin/python .claude/skills/extract-corpus/scripts/extract.py:*), Agent
---

# extract-corpus (Stage 2)

**A corpus file's body is the work's own content as the engine read it**, in
Obsidian Markdown, under the frontmatter and the PDF link Stage 1 wrote:
headings from the PDF's outline, prose as paragraphs, notation as LaTeX
notation spans, footnotes as `[^k]` marks with their definitions under a `# Notes`
heading at the end of the corpus file, and the bibliography one entry per paragraph.
It carries nothing that is not the work except a page marker where each page
begins: no title or
copyright page, no contents, acknowledgements, or list of illustrations, no
index, and nothing after the index.

**The engine is marker**, a vault dependency, run in-process from the script,
with its OCR off for a born-digital PDF and for each unit of a scan its layer
sample reads from the text layer. The engine supplies the page's
layout: what each block is, where it sits, and in what order the blocks read.
**On a text-layer page, the text layer supplies every character.** Each
visual line belongs to the one block whose box holds most of it, and a block's
text is built from its own lines: the characters as the page sets them, with
bold and raised footnote marks from the font. **On a notation page, the
engine reads the page from pixels and supplies every character**, its notation
as LaTeX. A page with no usable text layer takes the engine's own reading.

**A corpus file carries no italics.** Emphasis on a word changes no meaning a
reader or a search needs.

## Notation

**A notation page is read from pixels; every other page is a text-layer
page.** A notation page sets at least 5 characters in a math font or from the
Unicode arrow and mathematical operator blocks. `extract` finds the notation
pages itself and reads them from pixels; the report names them under
`read_from_pixels`.

**A page read from pixels whose next file page is read from the text layer
carries no engine continuation onto it.** The engine converts the pages read
from pixels as one document of their own, so its continuation from such a page
points at the next page read from pixels, never at the next file page. The
writer joins a paragraph across that page break only by its rule for a
paragraph that breaks off mid-sentence.

**A notation span is LaTeX between `$` and `$`, or between `$$` and `$$` for a
displayed formula.** Every downstream rule that treats notation differently
from prose keys on these delimiters, and on the legacy `❲…❳` placeholder of
older corpus files: the page checks strip the spans before the quality gate,
Stage 6 strips them before embedding and never cuts a chunk inside one, and
Answer questions verifies a quotation's prose with them removed.

**The notation guard checks every formula the engine reads against the text
layer before the formula is written.** A formula the text layer confirms is
written as the engine read it; a formula whose symbols or letter alphabets the
text layer contradicts in a few consistent places is corrected to the text
layer's; any other formula is written as the engine read it and flagged. The
report's `notation_log` names every corrected and every flagged formula by
file page.

**The prose guard checks the prose of every notation page against the text
layer.** If the engine reads a word that differs, in at most one letter in
four, from the same-length word the text layer aligns with it, the word takes
the text layer's spelling. NEVER apply the prose guard to a page whose text
layer lies invisibly under the page image: that text layer is an earlier OCR,
and its misreadings would replace the engine's.

**The numeral guard takes a numeral's digits from a text layer that lies
invisibly under the page image.** If the engine reads a token that mixes
digits with lowercase letters where that text layer aligns a token of digits
alone, and every digit the engine read stands in the layer's token in the
same order, the token takes the text layer's digits. NEVER take a word's
letters from such a text layer, and NEVER replace a capital: the numeral
guard corrects digits alone.

**A notation span is the engine's reading, checked by the notation guard, and
never a verified transcription.** A flagged formula, and a misread the text
layer shares, reach the corpus file unchecked. NEVER quote a notation span as
the work's notation: the notation is read on the PDF page the span's page
marker names.

**The report's `notation_blocks` counts, per file page, the `Equation` and
`TextInlineMath` blocks the engine labelled.** The notation page rule reads
the text layer alone; the counts are recorded for the rule's next revision,
and no step reads them.

**The rules for math fonts and notation spans are in
`reference/notation.md`.** The script applies them; the orchestrator applies
none.

**The script is `extract.py`.** Every command below is
`~/.research-vault/venv/bin/python .claude/skills/extract-corpus/scripts/extract.py <subcommand>`.
`<pdf>` is a library filename or a path.

| Subcommand | Writes | Does |
| --- | --- | --- |
| `probe <pdf>` | nothing | prints, as JSON, whether the corpus file and its body exist, the page count, the pages with a text layer, whether the PDF is a scan, the flags it recommends, the outline headings, and the font repairs recorded in the PDF |
| `convert <pdf>`, with `--force-ocr`, `--force-ocr-pages <ranges>`, or `--fresh` | the engine's output, into its cache in the scratch directory | runs the engine over the whole PDF, so that `scope` lists the pages the engine labelled and the later `extract` converts nothing again; `--fresh` discards the cache first; if an engine request fails, caches nothing and exits 1 naming `FailedInferenceRequests` |
| `layer-sample <pdf>` | the sample pages' pixel reading, into its own cache in the scratch directory | runs the layer sample on a scan, by *The layer sample*, and prints, as JSON, its `reads`, `layer` or `pixels`; its `pixel_pages`; the `flags` steps 2 and 3 pass; the pages with a text layer and the page count; and each unit with its first and last file page, its reading, and each sample page's agreement and notation spans; reads no page from pixels if the text layer is too thin; if an engine request fails, exits 1 naming `FailedInferenceRequests` |
| `scope <pdf>`, with `--page <file page>`… | nothing | prints the scope listing, as JSON: the work's `title`, `author`, `year`, `orig_year`, and `type`; every outline section of level 1 or 2 with its entry `<file page>: <title>` and its first and last file page; under `pre_labelled`, every run of pages the cached engine output labels `TableOfContents` or `Bibliography`, every run of pages holding no body block, labelled `blank`, and every index, labelled `index`, from the page an outline entry naming an index opens or whose opening lines print an index heading over alphabetized entries carrying page numbers, to the last page of entries that follows; `null` where no cache holds the work and no index is found; and every page to judge, listed under *The pages `scope` lists*, and every page a `--page` names, with its printed folio, its render, and its text-layer lines, less every line that recurs, identical but for its digits, among the first or last three lines of most of 40 pages sampled evenly from those holding more than six lines; if a `--page` names no file page of the PDF, exits 1 |
| `extract <pdf> --trial --exclude '<start>' '<resume>'…`, or `extract <pdf> --trial --exclude-nothing`, with the flags `--help` lists | the trial, with its page markers and the extraction record in its frontmatter, and the extraction's report beside it; without `--trial`, the corpus file's body, and the same record without a `reviewed` date, in the extraction records file | resolves the scope, converts, rebuilds, applies the page checks, then writes; if neither `--exclude` nor `--exclude-nothing` is given, or a point opens no line of its page or more than one, or a span resumes before it starts, writes nothing and exits 1 naming the scope or the point; if a doubtful page remains, writes nothing, prints the doubtful pages with their renders, and exits 2; if the body exists and neither `--trial` nor `--replace` is given, writes nothing and exits 1; if the corpus file changes on disk after the command reads it, writes nothing and exits 1 naming the file |
| `correction-listing <pdf>`, with `--body` | the pages file, `trials/<basename>.cleanup-pages.md`, and the text-layer lines file, `trials/<basename>.layer-lines.txt`, in the scratch directory | prints the correction listing, as JSON: the work; the text's path; the two files' paths; the outline headings; the scope; each page the cleanup reads, by *The cleanup*, with its file page, its page marker, its `flags`, and the `lines` of the pages file holding its text; and the collected notes those pages cite; with `--body`, the same for a reviewed work's corpus file; exits 1 if no trial exists, or, with `--body`, if the work is not reviewed |
| `correct <pdf> --corrections <file>`, with `--apply`, `--body`, and `--replace` | nothing; with `--apply`, the trial's body and its corrections file, `trials/<basename>.corrections.json`; with `--body --apply --replace`, the corpus file's body and the corrections in the work's extraction record | applies the corrections by *The cleanup* and prints each correction's outcome and the count of each outcome; if the corrections file is not a JSON list of well-formed corrections, writes nothing and exits 1; with `--body --apply` and no `--replace`, writes nothing and exits 1 |
| `accept <pdf>` | the corpus file's body from the trial, and the trial's extraction record, with today's date as `reviewed` and the trial's corrections, in the extraction records file | writes the trial's body into the corpus file and marks the work reviewed; if the corpus file holds a different body and `--replace` is absent, writes nothing and exits 1; a body equal to the trial's but for Stage 3's citation links is marked without `--replace` and keeps its citation links; if the corpus file changes on disk after `accept` reads it, writes nothing and exits 1 naming the file |
| `regress [<pdf>…]`, with `--sample <N>`, `--all`, or `--sample-set`, with `--baseline save` or `--baseline compare`, and with `--jobs <N>` | one diff per changed work, into the scratch directory; with `--baseline save`, each rebuilt body under `regressions/baseline/` there | rebuilds a sample of the reviewed works, or each work named, with its recorded scope and flags, from the engine's cache in `--jobs` processes at once, one fewer than the machine's cores unless `--jobs` says otherwise, then converts and rebuilds each work whose cache is absent, one at a time; diffs the rebuilt body against the corpus file's with Stage 3's citation links removed, or, with `--baseline compare`, against the body `--baseline save` kept; the sample is `N` random reviewed works, 12 unless `--sample` says otherwise, taken first from those whose engine output is cached and then from the rest, every reviewed work with `--all`, or the fixed sample set with `--sample-set`; prints the sample's counts, then each work, in the sample's order or the order named, as `unchanged`, `changed` with its diff path, its changed line count, and its `word_changes`, the words the rebuild adds or loses, `doubtful` with its doubtful pages, or `no-baseline` where `--baseline compare` finds no saved body; exits 3 if any work changed |
| `regress-sample`, with `--seed <N>` | the fixed sample set, `trials/regress-sample.json` in the scratch directory | chooses reviewed works by the properties their corpus file and extraction record show, three for each, five for footnotes, endnotes, and entry lists, taken first from works whose engine output is cached, then ten more at random; prints the set's count and the count for each property |
| `status` | nothing | lists the library PDFs whose corpus file has no body |
| `cache-check` | nothing | prints, as JSON, every cached conversion holding a page with no block: its basename, its mode, its cache file, its page count, and its empty file pages, the conversion with the largest share of empty pages first |
| `review-status` | nothing | lists the library PDFs whose corpus file has a body and whose extraction record carries no `reviewed` date |
| `record <pdf>` | nothing | prints the work's extraction record, as JSON, or `null` where the work has none |
| `labels <pdf>`, or `labels <pdf> --apply` | nothing; with `--apply`, the library PDF's page labels | plans one page-label range per run of consecutive folios the corpus file's page markers carry, and one empty range per run of pages with no folio; prints the plan and the PDF's current labels, and with `--apply` writes the plan into the PDF in place through a temporary file and prints the labels read back; if the corpus file has no body, writes nothing and exits 1 naming `accept`; if the corpus file carries `uncitable:`, writes nothing and exits 1 naming the field |
| `prefetch`, with `--works <N>`, `--keys <key>…`, and `--await-fonts` | the engine's cache in the scratch directory | walks the backfill queue, or only the lines `--keys` numbers, cheapest first by *The engine cost*, works of one cost in queue order, and converts each work into the cache with the flags `drive-prep` would pass, by the work's state, skipping a work reviewed, carrying a body, or already cached, and a scan whose layer sample is due but not yet recorded, naming `text layer not yet sampled`; converts a work only once its state records its font repair: without `--await-fonts`, skips a work whose state records none, naming `font repair unsettled`; with `--await-fonts`, walks the unsettled works again every 30 seconds and converts each once its state records the repair; before each conversion, under the engine turn, if the process runs on a Mac without Metal, as inside the sandbox, or the model server it starts or attaches to does not answer its health check, converts nothing more, stops, and exits 4; stops after `N` conversions, or at the queue's end; if an engine request fails, caches nothing for the work, stops, and exits 4; prints the works converted, skipped with the reason, and failed, and under `halt` the failed requests' work and failure or `null`, as one JSON line |
| `stop-servers` | nothing | stops the engine's model servers and prints the pids it stopped as one JSON line; run it once, after the batch's last `extract` |
| `reap-servers` | nothing | waits for the model servers to fall idle, then stops them and prints the pids; `extract` starts one in the background, and the orchestrator NEVER runs it |
| `drive-queue` | the backfill queue, `queue.txt` in `~/.research-vault/cache/backfill/` | writes the PDFs `status` lists to the backfill queue, one to a line, cheapest first by *The engine cost*, and prints their count as one JSON line; halts and writes nothing while a live session holds the run lock, because a rewritten queue changes every work key |
| `costs <pdf>…` | the engine costs, `engine-costs.json` in the scratch directory | prints each inbox or library PDF's engine cost by *The engine cost*, as `[<engine time>, <page count>]`, or `null` where the PDF does not open, as one JSON line |
| `drive-prep <key>`, `drive-fonts-checked <key>`, `drive-trial <key>`, `drive-retrial <key>` | the work's state and files, in `works/<basename>/` beside the backfill queue, reached as `works/by-key/<key>/`, so a rewritten queue finds each work's state | runs the deterministic part of steps 1 to 6 on the work listed under `<key>`, by *The backfill driver* below, and prints one JSON line naming its `state`; exits 0 |
| `drive-wait <key>` | `step.json` and `step.pid` in the work's directory | waits up to 560 seconds for the running engine step of the work listed under `<key>` and prints its JSON line; prints `running` if the step still runs, `aside` if the step ended with no result; exits 0 |

**The pages `scope` lists** are these, each once:

1. every page from file page 1 up to the first section whose title names no
   front or back matter;
2. every page from the last such section's last page to the end of the PDF;
3. in a run of 1 or 2 longer than `MAX_WHOLE_MATTER_RUN` pages, only its
   first and last page and every page whose opening lines change kind;
4. every page up to the first outline section;
5. the first page of every section;
6. the first and last page of every pre-labelled run;
7. the last three pages.

**The engine's output is cached** in the scratch directory, keyed to the
PDF's fingerprint, so a second `extract` after a worker's readings or a code
fix does not convert again; `--fresh` discards the cache.

**A conversion during which an engine request failed is never cached.** The
engine retries a failed request, then returns its pages blank, so `convert`,
`extract`, `regress`, and `prefetch` refuse the whole conversion once any
request fails after its retries, and a backfill driver step halts on it: the
model servers failing one work fail every work. If a cache may predate this
rule, run `cache-check`: a healthy conversion leaves only a blank page empty.
For each listed conversion, read the render of each empty page through
`scope <pdf> --page <file page>`; if a render prints anything, convert the
work again with `convert <pdf> --fresh`, adding `--force-ocr` for a
`forced-ocr` conversion. Otherwise leave the conversion as it is. `convert` fills
the cache before `scope` reads it, and `labels --apply` re-keys it to the
rewritten PDF. `regress` converts a sampled reviewed work whose cache is
absent.

**The engine's model servers stay up between runs, and one `extract` loads
its models once.** The conversion and the quality gate share one loaded set. Run `stop-servers` after the batch's last `extract`:
NEVER stop the servers between two PDFs of one batch, because each stop costs
the next PDF a full reload.

**The model servers run as many slots as `engine_slots` of `machine.json`
names, 8 if the key is absent.** A slot is one request the engine's VLM reads at
once, and each slot holds its own context: 16 slots read about 17% faster than
8 and hold about 1.75 GB more, whatever the work's length. Set 16 only while
the machine runs nothing else heavy, as overnight. A conversion that finds the
running VLM server holding another slot count stops the model servers under its
engine turn, and the engine's client starts them again with the count the key
names, so a changed key takes effect at the next conversion. If the key is not
a positive whole number, the conversion refuses to start and names the key.

**Every `extract` and `convert` that converts a page starts an idle reaper in the background.** The reaper stops
the model servers once no server log has been written for five minutes, and
NEVER while an `extract` or a `prefetch` conversion is running. One reaper runs at a time. A reaped
server costs the next run one reload: the engine's client starts a server it
finds missing. The reaper is what ends a batch that ends without
`stop-servers`; it NEVER replaces `stop-servers`, which frees the models at
once.

**The engine converts one PDF at a time, on one engine turn.** Every
conversion, `extract`, `convert`, `regress`, the font repair's pixel check,
and `prefetch` takes the turn, an exclusive lock on `engine-turn.lock` in the
scratch directory, and gives it back when it ends; NEVER run two conversions
at once: the engine peaks near 8 GB. A conversion waiting for the turn marks
itself in `engine-waiting/`. A `prefetch` conversion yields: it takes the turn
only while no other process waits for it, so a run's engine step waits at
most for the one prefetch conversion under way.

**An `extract` or a `convert` whose conversion the cache holds whole takes no
engine turn.** It converts nothing, so NEVER let it hold the turn: a
`prefetch` would yield to it while the model servers stand idle. `--fresh`,
or a page the cache lacks in the mode the page is read in, makes it a
conversion that takes the turn.

**Conversion runs ahead of a backfill.** Right after `drive-batch`, the
`ingest` workflow starts `prefetch --await-fonts --keys` over the run's works, detached
under the key `prefetch`, and `drive-release` stops it with every process it
started. It fills the cache cheapest first by *The engine cost*, works of
one cost in queue order, while the section
scoper and the page reader hold the run's works, so
a run's `drive-prep` finds its work converted. A detached step needs no
worker beside its one start, so the conversions ahead never wait on the
workers the run dispatches. NEVER start `prefetch` by hand while a run holds
the run lock; outside a run, start it in the one command form the `ingest`
skill states, or it runs inside the sandbox without Metal and refuses to
start. A `prefetch` conversion records
its process in `engine-prefetch.json`, never in `engine-run.json`, so the
`ingest` preflight does not halt on it. NEVER let `prefetch` convert a work
before its state records the font repair: the repair may rewrite the PDF or
send the work to be read from pixels, and either discards the conversion.

**A conversion converts only the pages the cache lacks.** The cache holds
each mode's conversion page by page, for the PDF as it stands; a conversion
reuses every page the cache holds in its mode, and the cache merges the
pages it converts into those it holds. A cached conversion that does not
hold one page entry per page serves only its own page list.

**A trial is the body as `extract --trial` writes it into the scratch
directory, under `trials/`, before `accept`**: a whole note, the corpus
file's frontmatter with the extraction record added, then the body.

**The extraction record is what the scripts keep about how a body was
built**: its `scope`, the excluded spans; its `flags`, the conversion flags;
its `mode`, `forced-ocr` on a work read from pixels and absent otherwise; and
its `reviewed` date. A trial carries the first three in its frontmatter as
`extraction_scope:`, `extraction_flags:`, and `extraction_mode:`. `accept`
moves the record into the extraction records file,
`library/extraction-records.json`, one record per work under its basename.
`regress` rebuilds a work from its record, `probe` and `review-status` read
its `reviewed` date, and Answer questions reads its `mode` through `record`. NEVER
write the record into a corpus file: no reader of the note has a use for it.

**A corpus file's body is written once, by `accept`, from a trial the page
checks passed.** If the body exists, `extract` without `--trial`
and `accept` refuse it: `probe` still reports on the PDF, and only
`--replace` rewrites the body. Pass `--replace` only on the user's
instruction: contract §4 makes a corpus file written once. The frontmatter
survives every write.

**A reviewed work is a work whose extraction record carries a `reviewed`
date, the date `accept` wrote its body.** `probe` reports it under
`reviewed`. NEVER extract a reviewed work again
except on the user's instruction. A later code change is held to the test
that pins its defect class; `regress` checks it against a sample of the
reviewed works besides, and never against every one: the engine output of
the whole library is never kept, and never rebuilt.

## Precondition

A PDF is ready for this stage when all three hold: it sits in the library at
its final basename; its corpus file exists with the Stage 1 frontmatter and
the PDF link; the corpus file has no body, or the user asked for a rebuild.
If `probe` reports `reviewed`, Stage 2 has nothing to do for the PDF: go on
to the next PDF.
`probe` and `extract` refuse a PDF whose corpus file is absent and exit 1
naming Stage 1: run Stage 1 first. `extract` refuses a run that gives no
scope and exits 1 naming `scope`: step 2 settles the scope.
`status` NEVER lists a PDF in `library/volumes/`, and Stage 2 NEVER extracts
one.

## Steps

1. **Probe.** Run `probe <pdf>` and read its output whole.
   - If `reviewed` is set, the work is reviewed: go on to the next PDF.
   - If `scanned` is true, the PDF draws no text layer of its own: its pages
     carry none, or carry an earlier OCR laid invisibly under the page images.
     Run `layer-sample <pdf>` and pass the `flags` it prints in steps 2 and
     3, by *The layer sample*; if it fails, take the branch step 3 gives the
     same failure. Every equation the engine reads from pixels is the
     engine's reading alone.
   - An outline entry whose title is only a page reference (`p. 166`), or
     only a numeral in an outline whose every numeral-titled entry that
     targets a page printing a folio, two or more, lies within one of that
     folio, names a page
     and no division: `probe`, `scope`, and `extract` read no heading from
     it, and a work whose every entry names a page has no outline.
   - If Stage 0's font repair could not settle the work's codes, by the
     `clean-pdfs` skill's "Codes the font repair cannot settle", the text
     layer cannot be trusted: pass `--force-ocr` in step 3, and run no layer
     sample.
   - If `headings` is empty and the frontmatter's `type:` reads
     `journalArticle` or `bookSection`, continue: the article's headings come
     from the engine alone.
   - If `headings` is empty and `type:` reads anything else, Stage 0 has
     given the work no outline: dispatch `pdf-bookmarker` on the library PDF
     as the `clean-pdfs` skill's "Stage 2 bookmarks a filed work it finds
     without an outline" states, then run `probe` again. If the worker
     reports `no-divisions`, extract the work as one chapter: its headings
     come from the engine alone, as an article's do. If the worker fails, or
     `headings` is still empty after it wrote an outline, write no body:
     report the PDF to the user and go on to the next PDF.
   - If the frontmatter names no `type:`, stop and ask the user.
2. **Scope.** Run `convert <pdf>` with the flags step 1 chose, one PDF at a
   time; if it fails, take the branch step 3 gives the same failure. Then run
   `scope <pdf>` and write its output, the scope listing, to a file in the
   scratch directory. If `scope` exits non-zero, set the PDF aside with the
   error as its question.
   - Dispatch the `section-scoper` worker: invoke the Agent tool with
     `subagent_type: section-scoper` and `model: claude-sonnet-5`, with the path of
     the scope listing and the path of a verdicts file in the scratch
     directory.
   - If the verdicts file is missing, is not JSON, or its `pages_judged` omits
     a page the listing names, dispatch the worker again once; if the second
     file fails too, stop and ask the user.
   - If a span's `see` names a page the listing does not name, or a span runs
     across a page the listing does not name, run `scope <pdf>` again with a
     `--page` for each such page and for every page added before, write its
     output over the scope listing, and dispatch the worker again with a note
     naming the pages added. Settle the new verdicts afresh.
   - If a span is flagged ambiguous and the listing names every page the span
     starts on, crosses, or names in `see`, dispatch the worker again once,
     with the span's start and resume points and the worker's reason as its
     note.
   - If the verdicts after that note flag a span ambiguous, keep its stretch:
     leave the span out of the scope, and report its start and resume points
     and the worker's reason with the work's notes. NEVER settle a flagged
     span by excluding it.
   - If the worker has been dispatched three times for one PDF and the
     verdicts call for a further dispatch, stop and ask the user.
   - The scope is `--exclude '<start>' '<resume>'` for every span the worker
     did not flag; if no span remains, the scope is `--exclude-nothing`.
     `accept` records the scope in the extraction records file; nothing else
     writes it.
3. **Extract.** Run `extract <pdf> --trial` with the scope step 2 settled and
   the flags step 1 chose, and pass the same scope to every later `extract`
   on the work. Run one PDF at a time, as `CLAUDE.md` §4 requires.
   - If it exits 1 naming a point, dispatch the worker again once, with the
     refusal in the prompt; if `extract` refuses a point of the second
     verdicts file, stop and tell the user.
   - If it exits 0, go to step 4.
   - If it exits 2, a doubtful page remains: resolve each page by the page
     checks below, then run `extract` again with `--readings <path>`, once.
   - If it exits 2 again, read from pixels the whole level-1 chapters of
     `probe`'s headings that hold the doubtful pages, never a part of one: add
     them to the work's one `--force-ocr-pages`, discard the readings, and
     run this step again, once per work. If no chapter is added, because each
     is already read from pixels or the work carries `--force-ocr`, or if a
     doubtful page remains after the readings of that run, stop and tell the
     user which pages remain.
   - If it exits 1 naming a missing PDF or a missing corpus file, stop and
     tell the user. If it exits 1 saying the corpus file changed on disk, run
     the same command again, once; if the change recurs, stop and tell the
     user. If it exits 1 naming `extraction-records.json` as not valid JSON,
     stop and ask the user: every work's record is in that file. If it exits 1 naming the scope, run step 2, then this
     step again. If it exits 1 naming a malformed readings file, dispatch the
     worker again for the same pages, once; if the second file is also
     malformed, stop and tell the user.
   - If it fails naming offline mode or a model the Hugging Face cache lacks,
     the engine's models are not installed on this machine: stop and ask the
     user to run the model step the README states.
4. **Verify.** Grep the trial for its heading lines. Every heading of
   `probe`'s outline that names content MUST appear as a heading line, in
   the outline's order; a heading inside an excluded span MUST NOT. Read the
   report's `footnote_log`: every entry names a mark the script left in
   place, or a footnote it wrote under `# Notes` without a mark, rather than
   pair. Read the report's `notation_log`; if it
   holds a flagged entry, name the flagged formulas' file pages to the user
   in the batch report, and change nothing. Read the report's `folio_log`:
   every entry names a page whose folio signals disagree, with both
   readings; name the pages in the batch report, and change nothing. If a
   heading is missing, name it in the batch report and change nothing.
   NEVER read the trial whole: it is a book.
5. **Accept.** Run `accept <pdf>`. NEVER hold a trial the page checks
   passed for a review or a code fix: the page checks keep garbled text out,
   and `CLAUDE.md` §1's quotation rule guards every citation against a
   layout the extraction got wrong. If `accept` exits 1 naming an existing
   body, stop and tell the user, and re-run with `--replace` only if the user
   asks for the rebuild.
6. **Label.** Run `labels <pdf>` and read its plan, then
   `labels <pdf> --apply`: the library PDF's page labels become the folios
   the page markers carry, so Zotero's reader, Preview, and Annotate show the
   printed folio the corpus file cites. If `labels` exits 1 naming
   `uncitable:`, the work gets no labels: go on to the next PDF. If
   `--apply` fails, report the failure in the batch report and go on: the
   corpus file stands, and the PDF is untouched.
7. **Pass B, for a chapter the engine misread.** If the user, reading the
   corpus file, finds a chapter whose text the engine garbled, run
   `extract <pdf> --force-ocr-pages <first>-<last> --replace` on the user's
   instruction, with the chapter's file pages from `probe`'s headings. NEVER
   force a page range that is not a whole chapter: the engine joins
   paragraphs across pages, and a seam inside a chapter corrupts the join.
   The rewrite clears the work's `reviewed` date: tell the user, and accept
   the work again on the user's instruction.

**A work with a body and no `reviewed` date is accepted on the user's
instruction**: run steps 2 through 6 on it. If `accept` exits 1 naming an
existing body, the trial differs from the body: show the user
`regress`'s diff for the work and re-run `accept --replace` only if the
user asks.

## The layer sample

**A scan is read from its text layer wherever a sample of its pages, read
from pixels, matches that layer.** A scan's text layer is an earlier OCR;
`layer-sample <pdf>` measures it against the engine's own reading of the same
pages, and its `flags` read from pixels every sample unit the layer does not
match.

| Term | Rule |
| --- | --- |
| coverage | a scan is sampled only if 80% or more of its file pages carry a text layer; otherwise `layer-sample` reads no page and prints `--force-ocr` |
| sample unit | a run of whole level-1 chapters of the outline, at least 20 pages long, the last unit taking any shorter remainder; a work without an outline is one run of chapters |
| sample page | one of 3 file pages per sample unit, spaced evenly among the unit's pages whose text layer holds 80 words or more |
| agreement | the share of the pixel reading's words, in their order, that the text layer's words match: letter runs in any script, case folded, a word broken by a line-end hyphen rejoined, notation spans removed |
| unit read from the layer | a sample unit whose every sample page agrees at 0.93 or more, and none of whose sample pages' pixel reading holds 5 or more notation spans |

| Units read from the layer | `reads` | `flags` |
| --- | --- | --- |
| every unit | `layer` | none |
| some units | `layer` | `--force-ocr-pages` over every page of every other unit |
| no unit, or no sample, as on a thin text layer | `pixels` | `--force-ocr` |

**NEVER read a scan's text layer without its layer sample:** the quality
gate passes most pages an earlier OCR misread, and only the engine's own
reading of a page shows the misreading.

**NEVER let a sample page enter the cache of the pixel conversion:** a unit
read from pixels is converted as one document, and a page already cached
would leave a seam inside its chapter. `layer-sample` caches its pages under
their own mode, `layer-sample`.

**A unit read from the layer is a run of text-layer pages.** The text layer
supplies every character, as on a born-digital PDF; the notation pages, the
page checks, and the doubtful-page steps apply unchanged, and the prose guard
and the numeral guard keep their rules for a text layer that lies invisibly
under the page image.

## The engine cost

**A work's engine cost is two numbers, compared in order: its engine time,
then its page count; the lower cost is the cheaper work.** The engine time is
its predicted pixel pages times 100, plus its other pages: a page read from
pixels costs the engine minutes where a page read from the text layer costs it
a second. NEVER rank by predicted pixel pages alone: a long book read from its
text layer then ranks ahead of a short work with a few pixel pages, though the
engine spends longer on the book. The backfill queue, a batch's listing, the
prefetch, and the engine turn each take the cheaper work first.

| The work | Predicted pixel pages |
| --- | --- |
| its state records `--pixels-only`, or its PDF reads as a scan whose state records no layer sample reading the layer | every page |
| otherwise | its notation pages, with every page its state records under `--pixel-pages`, which holds the units a layer sample reads from pixels |

**The engine costs cache what the PDF alone predicts:** its page count,
whether it reads as a scan, and its notation pages, under its basename and its
fingerprint, in `engine-costs.json` in the scratch directory. A PDF rewritten
since, by the font repair or the outline, is read again; a work's state is read
each time a cost is asked for. A PDF that does not open has no cost and ranks
after every work that has one. The cost of a work whose font repair has not run
counts its notation pages alone: the pages its unsettled codes send to pixels
are known only once the font scan has run.

## The ingest workflow

**Stage 2 runs through the `ingest` workflow, `.claude/workflows/ingest.js`, for a batch and for a backfill alike.** A batch carries each PDF from Stage 0 into Stage 2 on the basename Stage 1 filed it under. A backfill starts at Stage 2:

1. Run `drive-queue` as a background command; it writes the backfill queue, every library PDF whose corpus file has no body, cheapest first, and prints its count. A PDF the engine costs have not read takes about two seconds, so the first ranking of a large library outruns the Bash tool's ten-minute limit.
2. Invoke the Workflow tool with `name: ingest` and `args: {"from": "extract", "start": <first key>, "end": <last key>}`; a work's key in a backfill is its line number in the queue. A run SHOULD name at most 55 keys: one run dispatches at most 1,000 workers, a work takes about eleven, Stage 4's among them, and the tail up to 360.
3. If a run's range ends before the queue's last line, run the next range once the run returns.
4. Read the run's report as the `ingest` skill states it: each `placed` work is an accepted and classified work, with its notes; every set-aside work carries its `question`.

**A backfill repairs each work's fonts before its conversion.** If `drive-prep` prints `fonts`, the workflow runs the font repair by the `clean-pdfs` skill's "The ingest workflow" section on the library PDF: `drive-fonts`, a `glyph-reader` dispatch per group, then `drive-learn`. If the font repair ends in `bookmark`, the workflow runs `drive-fonts-checked`, adding `--pixel-pages <pixel_pages>` if the line carries `force_ocr` true and `pixel_pages`, or `--pixels-only` if it carries `force_ocr` true alone, then `drive-prep` again, so that `prefetch` may convert the work while its `drive-prep` waits for the engine; if `drive-fonts-checked` prints any `state` but `fonts-checked`, the work takes that line's outcome; otherwise the work takes the font repair's outcome. A batch's works passed Stage 0's font repair, so in a batch the workflow runs `drive-prep --fonts-checked` without repairing, adding `--pixels-only` if Stage 0 could not settle the work's codes. A work `drive-prep` skips is never repaired: its corpus file carries a body.

**The workflow keeps the engine to one PDF at a time.** Every `drive-fonts`, `drive-prep`, `drive-trial`, and `drive-retrial` waits its turn on the engine, and its turn holds every `drive-wait` until its result. The section scoper and the page reader of one PDF run beside the engine work of the next. On a backfill, the run's `prefetch` takes the engine turn whenever no step waits for it, so the engine still converts one PDF at a time. Two `ingest` runs share no turn on the engine, so the run lock the `ingest` skill states halts a second run before its first step.

**When the engine frees, the turn goes to the waiting step that ranks first,** by three keys in order:

1. A step of a converted work, `drive-trial` or `drive-retrial`, ranks before a step of a work not yet converted, `drive-fonts` or `drive-prep`: NEVER let a stream of new works hold back a work near its end.
2. Among steps of works not yet converted, the step of the cheaper work ranks first, by the `costs` `drive-batch` lists and *The engine cost* compares; a work it lists no cost for ranks last. NEVER rank a costlier work ahead of a cheaper one: its conversion would stop the run's stream of finished works.
3. Among steps tied on both keys, the step of the lowest work key ranks first.

**No step waits for the engine forever.** A run carries only the works `drive-batch` listed, each takes a bounded number of engine steps, and a work enters the first rank only through its conversion, which waits behind every converted work's step. The costliest work takes its turn once no cheaper work waits.

**If the Workflow tool is unavailable, run steps 1 to 6 by hand**, with the same `drive-*` calls in the order the table below names.

## The backfill driver

**The `drive-*` subcommands run Stage 2's deterministic steps, one call per step, and carry no judgment.** A workflow's dispatch runs one subcommand and relays its JSON line. The orchestrator, or the workflow, dispatches the section scoper and the page reader between calls, each writing to the path the previous line names. Each `state` names the next call:

| Subcommand | Runs | `state` and next call |
| --- | --- | --- |
| `drive-prep`, `drive-trial`, `drive-retrial` | the start of the step's engine work as a detached process, so the work outlives the Bash tool's 10-minute command limit, then the wait for its result, as `drive-wait` waits | the step's own `state`, by its row below; `running`: run `drive-wait` until its `state` is not `running`, all inside one turn on the engine; a second start while the step runs starts nothing and waits as the first |
| `drive-wait` | the wait for the running step's result | the step's own `state`, by its row below; `running`: run `drive-wait` again |
| `drive-prep` | steps 1 and 2 up to the dispatch; for a scan whose layer sample is due, `layer-sample` first, its JSON kept as `layer-sample.json` in `works/<basename>/` and its `reads` and `pixel_pages` recorded in the work's state, which every later `drive-prep`, `drive-trial`, `drive-retrial`, and `prefetch` of the work converts by | `fonts`: the work's state records no font repair; run the font repair, then `drive-fonts-checked`, then `drive-prep` again; `unbookmarked`: the work has no outline its type needs, and `kind` names the kind the bookmarker treats it as; bookmark it by the `clean-pdfs` skill's "Stage 2 bookmarks a filed work it finds without an outline"; `ready`: dispatch the section scoper on each of `parts`, then `drive-trial`; `skip`: go on to the next PDF |
| `drive-fonts-checked`, with `--pixels-only` or `--pixel-pages <listing>` | the record, in the work's state, that its font repair is done; with `--pixels-only`, also the record `drive-prep --pixels-only` makes; with `--pixel-pages`, also the file pages the listing names, which every later `drive-prep`, `drive-trial`, `drive-retrial`, and `prefetch` of the work converts with `--force-ocr-pages`, reading every other page from its text layer | `fonts-checked`: run `drive-prep` again; `aside`: the listing names no page; `drive-prep --fonts-checked` makes the same record, then prepares, in one call |
| `drive-prep --one-chapter` | the record, in the work's state, that `pdf-bookmarker` found no chapter opening, then the preparation | as `drive-prep`; the work is extracted as one chapter without an outline, and the record stands for every later `drive-prep` |
| `drive-prep --pixels-only` | the record, in the work's state, that the font repair cannot settle the work's codes, then the preparation | as `drive-prep`; the record stands for the font repair, and every later `drive-prep`, `drive-trial`, `drive-retrial`, and `prefetch` of the work converts it with `--force-ocr` |
| `drive-prep --cleanup` | the record, in the work's state, that its trial goes through the cleanup; every `drive-prep` without `--cleanup` records that it does not | as `drive-prep` |
| `drive-cleanup` | steps 3 to 5 of *The cleanup* on the trial, then steps 5 and 6 | `accepted`, with `notes`, the cleanup's counts among them; `recleanup`: dispatch the layout corrector on each of `parts`, which name only the pages the corrections files left unread, then `drive-cleanup` |
| `drive-trial` | step 2's settlement, and steps 3 to 6, or step 1 of *The cleanup* where the work's state records it | `accepted`, with `notes`, each kept doubted stretch, missing heading, and report finding among them: go on to Stage 3, or to the next PDF; `cleanup`: dispatch the layout corrector on each of `parts`, then `drive-cleanup`; `doubtful`, with `batches`, naming each batch's pages `listing` and its `readings` file: dispatch the page reader once per batch, then `drive-retrial`; `rescope`: dispatch the section scoper with `note` on each of `parts`, cut from the scope listing `drive-trial` rewrote if it added pages, then `drive-trial`; `rejudge`: dispatch the section scoper on each of `parts`, which name only the pages the verdicts left unjudged, then `drive-trial` |
| `drive-retrial` | step 3 with `--readings`, and steps 4 to 6; if a doubtful page remains, step 3's run with the doubtful pages' chapters read from pixels, once per work | as `drive-trial`; `aside` if a doubtful page remains after that run's readings; `unwritten` if a pages listing has no readings file, or the readings hold none: dispatch the page reader on every batch again once, then `drive-retrial`; a second `unwritten` sets the PDF aside |

**Every scope listing the drivers write is cut into parts of at most 12
pages,** `scope-part-<n>.json` beside the whole listing, and each line that
dispatches names `parts`: its `count`,
and the `listing` and `verdicts` file names in the line's `dir`, in which
`{n}` stands for the part's number, 1 to `count`. Dispatch one worker per part, all at once:
a worker's cost grows with the square of the pages it reads in one
conversation. Each part carries the whole listing's other keys, and
`look_ahead`, the first page of the next part, on which a span still open at
the part's last page resumes. The next driver call joins the spans of every
part into one verdict.

**A verdict that leaves listed pages unjudged is repaired in place.** The
driver sends only those pages, as `rejudge`, and joins the new verdicts with
the first. A scope run whose pages stay unjudged after one repair ends as
`rescope`, and counts toward the three scope runs.

Every `drive-*` subcommand but `drive-queue` takes the work as its work key, the number `ingest.py drive-batch` lists it under, or as its library basename; a basename needs no listing. A work addressed by its key keeps its files in `backfill/works/by-key/<key>/`, a link to `works/<basename>/`, so that every path the subcommand prints carries the key and never the name.

If a call prints `aside`, set the PDF aside with the line's `question`.
If a call prints `halt`, stop the batch with the line's `question`: the
engine's models missing from the cache, engine requests that failed, or an
extraction records file that does not parse, recurs on every work.

**The drivers take no by-hand branch.** A section scoper still calling for a
further dispatch after its third, a doubtful page left after the readings of
the run that read its chapter from pixels, and a readings file the page
reader wrote malformed each set the PDF aside.

## The cleanup

**The cleanup rearranges a text's words into a readable layout and NEVER
changes one.** It runs on a trial before `accept` when a batch passes
`cleanup: true`, and on a reviewed work's corpus file on the user's
instruction. It reads text alone, never a page image, and only the pages a
script doubts.

**A correction is one rearrangement**, by one of eight ops: `split`, `join`,
`move`, `drop`, `role`, `to-note`, `pair`, and `restore`, each with the
fields and limits the `layout-corrector` worker instructions state.
`correct` applies each correction and refuses it if it would change the
text's letters, except the furniture a `drop` deletes and the text-layer
lines a `restore` copies. A correction's outcome is `applied`; `stale`, the
text already reads as the correction would make it; `unmatched`, its anchor
matches nothing on its page; or `refused`, its anchor matches more than one
place, it breaks a limit of its op, or it would change a letter.

**The pages the cleanup reads** are each page of the text that one of these
holds, each named in the page's `flags`:

| Flag | The page |
| --- | --- |
| inside an entry list | holds text under a bibliography or notes heading |
| named in the footnote log | the report's `footnote_log` names it |
| a paragraph breaks off | a paragraph ends mid-sentence and the next opens in lowercase, on the page or across its page break where the page marker stands on its own line |
| a short line recurs | its first or last line, eight words or fewer, recurs at the edge of three or more pages, digits aside |
| a bare numeral | a paragraph is a numeral alone |
| a numbered paragraph | a paragraph opening with a number or a note sign closes the page |

1. Run `correction-listing <pdf>`, with `--body` for a reviewed work. If it
   lists no page, the cleanup has nothing to do.
2. Dispatch the `layout-corrector` worker once per part of at most 25 of the
   listing's pages, all at once: invoke the Agent tool with
   `subagent_type: layout-corrector` and `model: claude-sonnet-5`, with the
   path of the part and the path of a corrections file in the scratch
   directory.
3. If a corrections file is missing, is not JSON, or its `pages_read` omits
   a page its part names, dispatch the worker again once for those pages; if
   the second file fails too, go on without corrections for those pages and
   name them in the batch report.
4. Join the parts' corrections into one corrections file, and drop each
   correction `correct` would refuse as malformed, naming the count in the
   batch report.
5. Run `correct <pdf> --corrections <file>` and read the outcomes, then
   `correct <pdf> --corrections <file> --apply`; for a reviewed work, add
   `--body`, and `--replace` to its writing form. NEVER dispatch the worker
   again for a refusal: the text stands as it is.

**`accept` records a trial's applied corrections in its extraction record**,
and `correct --body --apply --replace` adds a reviewed work's to its record;
the corrected body keeps its citation links and its `reviewed` date.

## Refactoring the extraction code

**A refactor of the extraction code changes no word of any rebuilt body.**
Every refactor pull request passes this gate before it opens:

1. If the fixed sample set does not exist, run `regress-sample`.
2. On `main`, run `regress --sample-set --baseline save`.
3. On the refactor's branch, run `regress --sample-set --baseline compare`.
4. Every work MUST show `word_changes` 0, and no work that the baseline
   rebuilt MAY come back `doubtful`. Otherwise, narrow the change or drop
   it.
5. List each `changed` work in the pull request with its diff path and one
   judgment of its layout change: better, same, or worse. If most are worse,
   narrow the change or drop it.

## Fixing the extraction code

**The extraction code changes only on the user's instruction, never inside a
batch.** A batch accepts every trial the page checks pass; a defect the user
finds in a corpus file, or names from a batch report's notes, goes to the
extraction fixer when the user asks.

1. State the defect's defect class by `CLAUDE.md` §5. If no defect class can
   be stated, change nothing and tell the user.
2. Write the defects to a defects file in the scratch directory, as a JSON
   list, each with its `kind`, `file_page`, `observed`, `expected`, and
   `defect_class`, at most 12 to a file, grouped by defect class.
3. Check out the fix branch, by the rule under *The fix branch* below.
4. Dispatch the `extraction-fixer` worker: invoke the Agent tool with
   `subagent_type: extraction-fixer` and the session's model, with the path
   of the defects file, the path of a trial of the work, the path of the
   library PDF, the name of the fix branch, and the repository's root.
5. If the report says `unfixable` for a defect, tell the user the reason.
   If the report names a branch other than the fix branch, or reports no
   verdict for a defect, stop and ask the user.

**NEVER run a fixer's regression check while a batch runs**: `regress` takes
the engine turn for its whole sample, and the batch's next engine step waits
for it.

## The fix branch

**The fix branch is `extract-fixes/<YYYY-MM-DD>`, cut from `main`, and every
commit on it reaches `main` through a pull request.** NEVER commit an
extraction fix on `main`: CI and the review below gate every fix.

- **Before the first fixer dispatch**, run `git status --porcelain`; if
  it prints a line, stop and ask the user: a fix branch is never cut over
  uncommitted work. Then run `gh pr list --state open --json headRefName`;
  if an open pull request's head is a fix branch, `git switch` to it;
  otherwise `git switch -c extract-fixes/<today>` from `main`. If `gh pr
  list` or `git switch` fails, dispatch no extraction fixer and tell the
  user the failure.
- **After each extraction fixer reports**, if the checkout is on a fix branch
  that carries a commit `main` lacks, run `git push -u origin <branch>`, then
  `gh pr create` with the title `Extract: <the defect classes the commits
  fix>`, each named, or the class they share if they number more than
  three, NEVER the date or the batch,
  and a body listing each commit's first line and each changed reviewed
  work the commits name, ending with the line `🤖 Generated with [Claude
  Code](https://claude.com/claude-code)`; if the branch already has an open
  pull request, push, then retitle it with `gh pr edit <number> --title` to
  name the classes its commits now fix. Then `git switch main`.
- **If `git push` or `gh pr create` fails**, stay on the fix branch and
  tell the user the failure: the commits are safe on the branch.
- **Review the pull request once it is open.** For each commit, read its
  diff with `git show <sha>` and every regression diff its message names.
  Judge the commit against three questions: does the code do what the
  message states; is any rule, branch, or constant a special case; does any
  regression diff lose, duplicate, or garble text, or move it out of place.
  A regression is a change in a diff that leaves the rebuilt body further
  from the page than the corpus file.
- **NEVER merge a pull request whose CI has not passed**, as `CLAUDE.md` §4
  requires: if GitHub reports CI's jobs as not started, by a billing or
  runner failure, the pull request takes the Otherwise branch below.
- **If CI passes and the review finds no regression and no special case**,
  run `gh pr merge <number> --merge --match-head-commit <sha>` with the
  commit the review read, then `git pull` on `main`, then
  `git branch -d <branch>`; GitHub deletes the remote branch on merge. If
  `gh pr merge` or `git pull` fails, tell the user the failure.
- **Otherwise**, leave the pull request open and ask the user, naming each
  commit the review faulted and what it found. If CI has not finished,
  report the pull request as awaiting CI, and review and merge it on the
  user's next message.

## The section policy

**The body carries everything that bears on the work's content: everything
kept is embedded and searched.** What carries nothing of the content —
funding statements, acknowledgements, the publisher's pages, the index — is
the section scoper's judgment, passed to `extract` as the scope. NEVER add a
script rule that drops text by its heading's title or by its position before
the outline: no such rule tells a publisher's page from an editor's
introduction, or an acknowledgement from the body that follows it on the same
page.

**The section policy drops the scope's excluded spans and nothing else.** An
excluded span runs from its start point up to its resume point. A block the
engine found is dropped when the excluded spans cover more of its box than
they leave. An outline heading the engine did not find is dropped when its
destination lies inside a span. A transcribed page or an omitted page is dropped whole only
when one span covers the whole page, because it carries no block positions.

**An entry list is rebuilt from the text layer.** In a section headed
bibliography, references, works cited, notes, or endnotes, or one of the
equivalents `lib/_vault/citations.py` lists, the engine's paragraphs are
replaced by the text layer's lines grouped by their hanging indents, one
entry per paragraph, so Stage 3 finds each entry whole. A line opening the
longest run of consecutive note numbers always opens an entry: right-aligned
note numbers hang at more than one indent.

## The page checks

**The script checks every page, and the checks are language-independent.** A
page fails on any condition in the table.

| Condition | Reason reported |
| --- | --- |
| the page is read from its text layer yet has neither a text layer nor output, and neither `--force-ocr` nor `--force-ocr-pages` covers it | `no text layer and no output: pass --force-ocr` |
| the engine produced no text for a page whose text layer has text | `the engine produced no text for a page whose text layer has text` |
| the page is read from pixels, the scope does not cover the whole page, and the engine read no text from it | `the engine read no text from the page's pixels` |
| a notation span holds a wide letter, an East Asian letter or a full-width form, which no notation writes | `a notation span holds a wide letter, which no notation writes`, with the span |
| a passage of 120 characters repeats four times on the page | repetition |
| the output is shorter than half, or longer than two and a half times, the text layer's length, counted in visible characters on both sides | length |
| the page's prose, with notation, page markers, table markup, and emphasis marks stripped, measures `poor` or `unavailable` on the quality gate | the gate's reason |

**The quality gate is the engine's page classifier beside two hard
signals.** The classifier is surya's `OCRErrorPredictor`, the classifier the
engine runs on every page during conversion, served from the shared
`ocr_error` server that its client starts. The hard signals are the
alphabetic character ratio and the replacement-character ratio. A page
measures `poor` if the classifier reads it as bad or a hard signal fails.
NEVER drop the hard signals for the classifier: a broken font produces
mojibake the classifier has not seen. NEVER add a word list to the gate:
German, French, Latin, and Greek measure as English does.

**If the classifier's server cannot start, the gate measures `unavailable`
and the page is doubtful with the reason `classifier unavailable`.** If the
`extract` report's doubtful pages carry that reason, NEVER dispatch the
worker for them: read `ocr_error_server.log` in the engine's cache directory,
`~/.cache/datalab/surya` unless `machine.json` names another under
`surya_cache_dir`, then run `extract` again, once; if the reason recurs, stop
and tell the user.

**A page's folio is read from three signals, and a disagreement is a
finding, never a doubtful page.** The signals are the engine's header and
footer blocks, the text layer's own edge lines, and the PDF's page label, in
that order: the first signal that yields a folio is the page's. If the page
label disagrees with a printed folio on any page of the work, the label tree
is contradicted, and no page of the work takes its folio from a label. The
report's `folio_log` names every page whose signals disagree, with both
readings.

**A page takes exactly one of three branches.**

| Branch | Condition | Does |
| --- | --- | --- |
| 1. kept | every check passes; a worker's transcription passes the quality gate, the repetition check, and the hard signals, and is never measured against the text layer | the page is written as the engine read it, or as the worker transcribed it |
| 2. doubtful | a check fails | a worker reads the render visually; a transcription that passes the checks joins branch 1, one that fails is doubtful again with its reason, and the verdict `unreadable` joins branch 3 |
| 3. omitted | the worker returned `unreadable` | the page's text contributes nothing to the body and the page has no page marker; an outline heading due on the page still opens; the report lists its file page under `omitted_pages` |

**Resolving branch 2.** Dispatch the `page-reader` worker: invoke the Agent
tool with `subagent_type: page-reader` and `model: claude-sonnet-5`, with at most 20
pages per dispatch. The prompt MUST carry: the PDF's basename; for each page
its file page, its printed folio, and its render path from the `extract`
report; and the path of a readings file in the scratch directory for the
worker to write. The worker writes a JSON list of readings, one per page:
`{"page": <file page>, "text": "<transcription>"}` or
`{"page": <file page>, "unreadable": true}`. If the worker reports a page it
could not open, dispatch that page again, once; if the second dispatch also
cannot open it, treat the page as `unreadable`. If the worker returns no
readings file, or its output is marked partial, the dispatch failed: dispatch
again once; if that fails, stop and ask the user.

**The checks are per page and the worker is per page.** NEVER pass a page as
readable because its neighbours were; NEVER send a whole book to the worker.

## Guarantees on completion

* The corpus file's frontmatter is as Stage 1 and Stage 4 left it. The
  extraction records file holds the work's extraction record: its scope,
  its flags, its `reviewed` date, and `mode: forced-ocr` on a work read from
  pixels; a work read from its text layer records no `mode`.
* Every page of the body passed the page checks, and the batch report names
  each missing heading and each report finding the trial left.
* Where the engine's text or list blocks overlap, and one block's box holds
  text its html does not while the blocks together hold the text layer's
  text, those blocks are written from the text layer's lines instead: one
  paragraph per run of lines, a paragraph ending at a line that stops short of
  the margin, at a wider space, or at a line indented past the one above it,
  with the text layer's superscripts. Every other block is written
  as the engine read it.
* Every heading line is one heading of the PDF's outline, at the outline's
  level, prefixed by `#` per level; an outline heading that is a bare label
  (`Chapter 2`) absorbs the title printed under it. An outline heading the
  engine did not find opens at its destination's position on the page, and
  an outline entry is NEVER written twice. An outline heading due on a
  transcribed page opens where the transcription prints its title, and
  before the transcribed text where it prints it nowhere; one due on an
  omitted page opens in that page's place. A heading the engine found inside
  a section and the outline does not list sits below it, at a depth set by
  its printed size and weight, unless it ends in a colon, opens with a
  conjunction, or is a running head. A running head stands between no two
  text blocks, is set smaller than 1.2 times the running heads that print
  its words, and either repeats a running head the work prints, opens with
  the page's folio, names the work's title or an opened heading, or has its
  middle within the height the work's running heads span and is set smaller
  than 1.2 times their type. The work's running heads are the lines that
  open their column above a page's text, repeat one wording atop two or more
  pages, and set their middle within the height of the middle one of all such
  lines; if they stand atop no more than half the work's pages, the work has
  none. A candidate whose size and weight match a heading the outline lists is kept
  regardless.
* A page marker is `%% p. <folio> (file p. <N>) %%`, or `%% file p. <N> %%`
  where the page prints no folio. If a page begins at a block boundary, its
  marker sits on its own line before the heading, paragraph, equation, or
  table the page opens with. If a paragraph continues across the page, the
  marker sits inline at the first word boundary at or after the break: a
  word rejoined across the break is never split. A marker NEVER sits inside
  a heading line, a display equation, or a footnote definition; a footnote's
  page is the page of its mark. A page that contributes nothing to the body
  has no marker. The folio is the first that the three folio signals yield,
  by the rule under *The page checks*.
* After `labels --apply`, the library PDF's page labels are the folios the
  page markers carry, one range per run of consecutive folios and an empty
  range per run of pages with no folio; a work carrying `uncitable:` keeps
  the labels it had.
* Every footnote mark the text layer raises and the page defines is `[^k]`,
  with `k` unique across the corpus file, and every definition sits under a
  `# Notes` heading at the end of the corpus file; a mark the script could
  not pair stays in place, and a footnote block it could not pair sits under
  `# Notes` as `[^k]: <text>` with its printed number, if any, kept and no
  mark, so that Stage 3 links it; both are named in the report. A block the
  engine labels a footnote is a displayed body line, and stays in the body,
  only if it opens with a number in parentheses or brackets, is set at the
  body's type size, and the body of its page raises no mark with that
  number, neither the label itself nor a superscript digit. A mark
  whose footnote or endnote the scope excludes is dropped with it. A mark
  raised on a heading sits on its own line directly below the heading: a
  heading line NEVER carries a mark. Endnotes printed in a Notes chapter
  stay in that chapter, one entry per paragraph, and each endnote mark is
  one superscript.
* Every notation page is read from pixels, and its notation is written as
  notation spans the notation guard has checked; every text-layer page carries
  the text layer's characters, notation included, with no notation span.
* Every numbered statement the work sets as a bold run-in label — a
  definition, a theorem, a lemma, and their kin — opens as a heading carrying
  that label, and its text follows as the paragraph below.
* Every page written passed the page checks, as the engine read it or as a
  worker that looked at it transcribed it.
* No text of the work is lost to a heading: a table is a Markdown table, or
  its HTML when its cells span rows or columns, and a figure contributes its
  caption, and its labels, one line per row, if the text layer sets them
  mostly in words at the body's type size. NEVER write an image into the
  vault: a figure is read on its page.
