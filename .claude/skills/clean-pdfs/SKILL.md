---
name: clean-pdfs
description: "Stage 0 — on a PDF in the inbox: judge its kind, de-annotate it in place, repair its fonts, judge its cover, and bookmark it; font repair also runs on a filed PDF on the user's instruction."
allowed-tools: Read, Bash(~/.research-vault/venv/bin/python .claude/skills/clean-pdfs/scripts/clean.py:*), Agent
---

# clean-pdfs (Stage 0)

**Stage 0 judges what one PDF in the inbox is and remediates it in place.**
The inbox is `~/Desktop/inbox/`, and the cleaned file is the inbox file
rewritten: there is no second copy. Stage 0 NEVER puts a file in the library:
Stage 1 files the PDF from the inbox, and ZotMoov moves it into the library.

**Stage 0 is executed by three workers on Sonnet**: `pdf-cleaner`
(de-annotate, judge the cover), `glyph-reader` (name the characters a broken
font's glyphs stand for), and `pdf-bookmarker` (write the outline). In a
batch, the `ingest` workflow dispatches them and runs the font repair through
`drive-fonts` and `drive-learn`; outside a batch, the orchestrator dispatches
them and runs the font repair itself. Every rule a worker obeys is in its worker instructions. A `pdf-cleaner` prompt names one PDF. A `pdf-bookmarker`
prompt names one PDF, states whether it is an article, a book, or an edited
volume, and states that the cover work on it is final; for a PDF read from
pixels, it states that the text layer cannot be trusted; a range dispatch also
carries the page range, the checklist, the entries confirmed so far, and the
path of its entries file.

## Invariants

| Rule | Holds |
| --- | --- |
| Page geometry is never altered | no page is split, cropped, rotated, or resized; a two-up scan stays two-up |
| The inbox file is the file worked on | `clean --apply` rewrites it in place through a temporary file; if the check fails or the file is damaged beyond repair, the inbox file is untouched and no temporary file remains |
| Each command locates the PDF by name | `plan`, `clean`, `add-cover`, `drop-page`, and `volume` require it in the inbox; `render`, every `toc` subcommand, and every `fonts` subcommand take the first of the inbox, the library, and `library/volumes/` that holds it |
| Page geometry changes only in the inbox | `add-cover` and `drop-page` refuse a library or volume PDF: a page added or dropped after filing shifts every file page the outline, the corpus file, the card, and the annotations target |
| Annotations are stripped only in the inbox | `clean --apply` refuses a library or volume PDF: it strips every annotation, and a filed PDF carries the user's own, written by Annotate |
| One command has no dry run | `toc clear --apply` destroys the whole outline. Probe the outline and be certain before calling it; if certainty is not reached, stop and ask the user |
| Page numbers are 1-based | `render --page N`, `toc scan --from N --to M`, `drop-page --page N`, and an outline entry's `page` name the same file page |

## Cover policy

The judgment criteria, the search procedure, and the reject list are in
`.claude/agents/pdf-cleaner.md`. Two rules bind the orchestrator:

| Rule | Holds |
| --- | --- |
| A book or a volume with no cover is a finished file | if the report says it searched and found no genuine jacket, accept the file and dispatch step 6 |
| A report distinguishes "searched and found nothing" from "did not look" | if the report does not distinguish them, dispatch `pdf-cleaner` again on that file before step 6 |

## Procedure

Every command is `~/.research-vault/venv/bin/python .claude/skills/clean-pdfs/scripts/clean.py <subcommand>`.

| # | Step | Command | Who |
| --- | --- | --- | --- |
| 1 | Plan | outside a batch, the orchestrator runs `plan --all` once, to list the inbox; in a batch, `ingest.py drive-batch` lists it. Each `pdf-cleaner` runs `plan "<name>.pdf"` on its own file. `plan` prints one JSON report per PDF and render page 1 to `first_page_render` in the scratch directory; neither writes anything else | orchestrator, then `pdf-cleaner` |
| 2 | Judge the cover | Read the render. If the file is a book, decide whether page 1 is a real cover. If the file is an article, skip: it gets no cover either way | `pdf-cleaner` |
| 3 | Clean | `clean "<name>.pdf" --apply` — strips annotations and rewrites the inbox file in place through a temporary file. Without `--apply` it reprints the plan | `pdf-cleaner` |
| 4 | Drop scan cruft | `drop-page "<name>.pdf" --page <1-based>` prints the plan; the same with `--apply` deletes the page from the only copy, so render the page and be certain first. Only where the page's fault can be named; the fault list and the recovery are in `.claude/agents/pdf-cleaner.md` | `pdf-cleaner` |
| 5 | Find and add a cover | a book or a volume only, and only if step 2 found none: `add-cover "<name>.pdf" --image "<cover>"` prints the plan, and the same with `--apply` prepends the image as a full-bleed page, sized to the image's aspect ratio, and refuses an article, or a file whose page 1 is already image-only, without `--force`. If the confirmation render (`render "<name>.pdf" --page 1`) shows white bands, the image is wrong. If no genuine jacket is found, skip this step and report that it was searched for | `pdf-cleaner` |
| 5b | Repair the fonts | the procedure under "Font repair" below, after step 5 and before step 6 | the `ingest` workflow or the orchestrator; `glyph-reader` |
| 6 | Bookmark | every kind, in a second dispatch, after every cover decision on the file is final: `toc probe`, `toc fonts --page N`, `toc suggest --filter "<font>:<size>:<level>"…`, `toc scan --from N --to M`, `toc write --entries "<path>.json"` (dry run), then `toc write ... --apply`. `toc fonts` and `toc suggest` write nothing; `toc write` is the only writer of the outline. `toc clear --apply` destroys the whole outline and runs only on the user's instruction | `pdf-bookmarker` |

**Step 6 runs on every kind.** A book or a volume is bookmarked from its
printed table of contents, an article from the section headings printed in its
body. An article with no section divisions gets no outline: that is a correct
outcome, not a failure. A volume NEVER skips step 6: its outline is its
contents, and `extract-chapters` reads it. If a volume's outline cannot be
built, stop and ask the user.

**Step 6 finds openings by font before it walks.** `toc suggest` lists every
text line set wholly in a heading's font and size, chosen with `toc fonts`
from a rendered page, as a candidate entry list; the worker verifies the
candidates by rendering, and ticks them against the printed table of contents
where one exists. A scanned PDF sets every page in one OCR font, so its
candidates are useless: the worker walks it with `toc scan`.

**On completion**, `pdf-cleaner`'s report has judged the file an article, a
book, or an edited volume:

| The report judges the PDF | Do |
| --- | --- |
| an article or a book | proceed to `file-pdfs` (Stage 1) |
| an edited volume | after step 6, run `volume "<name>.pdf"`, read the plan, then run it with `--apply`, which moves the inbox PDF into `library/volumes/`; the volume gets no Zotero record, no corpus file, and no later stage. Its outline is its contents. `volume` refuses a PDF carrying no outline and moves nothing: bookmark it first. If the command reports that a file of that name is already among the volumes, it has moved nothing: stop and ask the user. Once the volume is moved, invoke the `extract-chapters` skill on it: the user chooses which chapters are cut into the inbox |

If the report names none of the three, stop and ask the user.

## Font repair

**A broken font is a font whose ToUnicode table names a character the page
does not show, or whose table lacks a glyph the page prints.** Font repair
rewrites the table in the PDF; no pixel changes.

**The pixel check finds a broken glyph by reading the page.** For every
glyph the text layer emits, `scan` samples up to three lines where the glyph
occurs, renders each line, reads the render, and compares what was read with
the character the text layer emits. A plain glyph, a Latin letter, a digit,
or a punctuation mark, is read by Apple Vision; every other glyph, a symbol,
a Greek letter, a Dingbats or Private Use Area character, is read by the
engine, whose LaTeX for a formula the check converts to Unicode. A glyph
disagrees when it has at least two samples and agrees on at most a tenth of
them; the disagreement carries a reading when one character accounts for at
least half the samples. A glyph that disagrees is a flagged code, as is a
code whose table names a Dingbats or Private Use Area character, a control
character, the replacement character, or nothing. If a font has neither a
table nor a Differences array, the text layer emits each glyph the reader
cannot name as its own code: `scan` takes the code from the character it
emits, and the repair writes the font a table from the patched codes.

**`scan` caches the pixel check under the scratch directory by the PDF's text
layer.** `identify` and `repair` reuse the cache, and a rewrite that leaves the
text layer unchanged — `clean --apply`, `toc write --apply` — does not force a
new check. A check that left an engine line sheet unread is never cached: its
glyphs on that sheet went unchecked, so the next `scan`, `identify`, or
`repair` runs the check again. If `scan` reports `unread_sheets` above 0, run
`scan` again before `identify`; if the second `scan` also reports
`unread_sheets` above 0, stop and ask the user.

**The identity table is `library/glyph-identities.json` in the
vault**: for a font family and a glyph name, or a glyph code where the font
names none, the character the glyph stands for, and who identified it. A
glyph name that names its own character — a small capital, an old-style
figure, a ligature, a `uniXXXX` name outside the two blocks — needs no table
entry. If the pixel check flags a code whose glyph name, read by the Adobe
Glyph List, its TeX names, or a `uniXXXX` or `uXXXX` name, is exactly the
character the text layer emits outside the two blocks, the glyph name settles
the code as that character: `scan` reports it with its reading and method
`glyph-name`, `codes_unresolved` omits it, and `identify` and `repair` pass
over it. A glyph name naming another character settles nothing. An identity holds across every work that uses the font family. An
empty string is the identity of a drawing fragment: the glyph leaves the text layer.

**An OCR text layer is never repaired.** An OCR text layer is a font the PDF
draws only as invisible text, or only on pages one image covers. `fonts scan`
flags none of its codes. NEVER learn an identity for a character an OCR text layer emits:
its code carries the recognizer's reading, not a glyph, so one identity
retypes every occurrence the recognizer read correctly.

Every command is `~/.research-vault/venv/bin/python .claude/skills/clean-pdfs/scripts/clean.py fonts <subcommand>`.
`--table <path>` before the subcommand reads and writes another table; it is
for tests and NEVER for a repair that changes a vault PDF. If `scan` fails
naming offline mode or a model the Hugging Face cache lacks, the engine's
models are not installed on this machine: stop and ask the user to run the
model step the README states. If `scan`, `identify`, or `repair` exits with
the status `vision-unavailable`, Apple Vision is not installed on this
machine: stop and ask the user to run the font repair on a Mac. If `scan`,
`identify`, or `repair` fails naming Apple Vision otherwise, the pixel check waited past its limit for one line's
reading and cached nothing: run the same command once more. If the second run
also fails naming Apple Vision, stop and ask the user.

| # | Step | Command | Does |
| --- | --- | --- | --- |
| 1 | Scan | `fonts scan "<name>.pdf"` | read-only; runs the pixel check, minutes for a book: every flagged code, with its font family, glyph name, current character, count, `source` (`rules` or `pixels`), the pixel check's `reading`, and identity or `null`; `codes_unresolved` counts the codes no rule and no table entry settles; a `missing-from-tounicode` row names a character no code can be traced to; `math_fonts` lists the fonts the text layer sets notation in, by `math_fonts.py` in `lib/`; `pixels` counts the lines read, the glyphs checked, and `unread_sheets`, the engine line sheets the check could not read |
| 2 | Identify | `fonts identify "<name>.pdf" > "<scratch directory>/<name>.identify.json"` | read-only: for every unresolved code, two or three renders of the glyph in its line, the text-layer context of each occurrence, the pixel check's reading, and the character the code emits today, with the paths under the scratch directory; step 4 reads the saved file |
| 3 | Read | dispatch `glyph-reader` | invoke the Agent tool with `subagent_type: glyph-reader` and `model: claude-sonnet-5`; the prompt names the saved `identify` output and the answers path, `<scratch directory>/<name>.answers.json`. NEVER restate the worker's instructions |
| 4 | Learn | `fonts learn-reader --answers "<name>.answers.json" --identify "<name>.identify.json"`, one `--identify` per PDF the answers name, then the same with `--apply` | one entry per identity the worker named, `=` learned as the character the saved `identify` output reports the code emitting today; lists, and writes none of, every `unresolved` glyph; every key the table already holds with a different character, or that two answers give different characters, under `conflicts`; every answer a row of "Learning an identity" sets aside, under `set_aside` with its `reason` (set the PDF aside); and every code with no glyph name, in a family publishers re-encode per document, that the worker answered `=`, under `needs_no_repair`; if the worker left a glyph `unresolved`, or `set_aside` lists an answer, learn nothing and read the PDF from pixels, by "Codes the font repair cannot settle"; an identity the user names on the user's own instruction is learned with `fonts learn --font <family> --glyph <name> --unicode "<character>" --method user`, or `--code <hex>` in place of `--glyph` for a code that carries no glyph name; the rules under "Learning an identity" bind every entry |
| 5 | Repair | `fonts repair "<name>.pdf"`, then `fonts repair "<name>.pdf" --apply` | the read-only form prints the patch plan and the unresolved codes; `--apply` rewrites the PDF in place through a temporary file, writes a table from its glyph names for a font that has none, records every patch in the PDF's information dictionary under `VaultFontRepair`, and verifies the text layer |

| `repair` status | Meaning | Do |
| --- | --- | --- |
| `nothing-to-repair` | no flagged code, or every flagged code already emits its identity | continue to step 6 of the procedure |
| `would-repair` | the read-only form; the plan is complete | run `--apply` |
| `unresolved-codes-remain` | a flagged code has no identity | read the PDF from pixels, by "Codes the font repair cannot settle"; `--apply --partial`, which patches the resolved codes only, runs only as "Learning an identity" states |
| `repaired` | the PDF was rewritten and verified | continue |
| `verification-failed` | the repaired text layer still emitted an old character; the file is untouched | read the PDF from pixels, by "Codes the font repair cannot settle" |
| any other value | unspecified | stop and ask the user |

### Learning an identity

**The identity table keys a glyph name and a glyph code apart**: a code under
`<family>|#<hex>`, a name under `<family>|<name>`. `fonts migrate-keys` prints
how the table's older unprefixed code keys would be rewritten, and `fonts
migrate-keys --apply` rewrites them. Run it only on the user's instruction;
if it lists a key under `ambiguous`, name the key to the user and change
nothing for it.

**An identity retypes the glyph in every work that sets the font family, so
every entry MUST hold for all of them.**

| Case | Do |
| --- | --- |
| the worker names a character only the work's use gives the glyph | learn the character the glyph's shape stands for; if the work's text then reads wrong, name it in the batch report |
| an identity for the same key is already in the table and differs | learn nothing for the key; keep the table's entry and name the conflict in the batch report |
| the code carries no glyph name, and its family fixes its own encoding: a TeX family (`CM*`, `EU*`, `MSAM*`, `MSBM*`, `LASY*`, `rsfs*`, `LINE*`) or a subset-hashed family | learn it |
| the code carries no glyph name, its family is one publishers re-encode per document (a Times, Symbol, Arial, Helvetica, Palatino, Garamond, Minion, Cambria, or Courier family), and the worker answered `=` | learn nothing for the code: it needs no repair. If no other code of the PDF is unresolved, skip step 5 and continue to step 6 of the procedure; otherwise run step 5 with `--apply --partial`, which leaves the code as it is |
| the code carries no glyph name, its family is one publishers re-encode per document, and the worker named another character | learn nothing for the PDF and read it from pixels: a code-keyed identity there retypes every other work in the family |
| the PDF carries more than 30 unresolved codes | learn nothing for the PDF and read it from pixels |
| any other case | learn nothing for the PDF and read it from pixels, naming the code and its family in the batch report |

### Codes the font repair cannot settle

**A PDF whose codes the font repair cannot settle is read from pixels.** The
font repair cannot settle a PDF's codes if `scan` counts more than 30
unresolved codes, if the glyph reader leaves a glyph `unresolved`, if
`learn-reader` lists an answer under `set_aside`, if `repair` reports
`unresolved-codes-remain` for a code `needs_no_repair` does not list, or if
`repair --apply` reports `verification-failed`. Then:

1. Learn nothing for the PDF, and repair nothing: its text layer stays as it
   is.
2. Continue to step 6 of the procedure. The text layer cannot be trusted, so
   the `pdf-bookmarker` prompt says so, and the worker takes every title from
   the render.
3. Stage 2 reads from pixels every page the text layer cannot be trusted on:
   - **In a backfill,** `fonts pages "<name>.pdf"`, read-only, prints the file
     pages any flagged code occurs on, or `null` where a flagged code's pages
     are unknown. If it names some pages but not every page, the font repair
     writes them to `pixel-pages.json` in the work directory, the `ingest`
     workflow passes `--pixel-pages <that file>` to `drive-fonts-checked`, and
     Stage 2 reads those pages from pixels and every other page from its text
     layer: a page no flagged code occurs on emits only characters the scan
     trusts.
   - **Otherwise, and in every batch,** Stage 2 converts the work by Pass B,
     whole-work, as it converts a scan: the `ingest` workflow passes
     `--pixels-only` to `drive-prep` in a batch, or to `drive-fonts-checked`
     in a backfill. NEVER pass a page listing in a batch: Stage 0 may add or
     drop a page after the font repair, and every listed page would shift.

   Either record stands in the work's state for every later conversion of
   the work.
4. Name the PDF and the reason in the batch report.

NEVER learn a code-keyed identity in a family publishers re-encode per
document to settle a PDF: the remedy is the PDF's own conversion, never a
table entry.

**A subset-hashed family is a family whose name ends in a run of six or more
hexadecimal digits, at least one of them a numeral, before an optional style
suffix of letters after a `.` or a `-`.** Its name is unique to one PDF, so a
code-keyed identity in it retypes no other work.

**`learn-reader` applies the rows above to every answer it reads.** It learns
nothing for an answer a row sets aside, and lists the answer under
`set_aside` with the row's reason.

**Pool a backlog outside the `ingest` workflow.** If more than one PDF
waits at step 3, dispatch one
`glyph-reader` per group of PDFs holding at most 45 codes, the prompt naming
each PDF's saved `identify` output and one answers path for the group; learn each group's identities with one
`learn-reader` run, one `--identify` per PDF of the group, before the next
group's repair.

**A `missing-from-tounicode` character cannot be repaired**: the font has
no table, and its encoding names no glyph for the character. Report it and
continue; Stage 2 checks such a page like any other.

**The backfill.** `fonts scan --all` lists every library PDF with a code the
Dingbats rule flags, read-only and without the pixel check. Repairing a filed PDF is the same procedure on the library
file, and it runs only on the user's instruction, one PDF or one named batch
at a time: a filed PDF is not the inbox file, and its rewrite is the
authorized overwrite `AGENTS.md` §5 names. A Stage 2 backfill the user
starts is that instruction for each work it converts: the `ingest` workflow
repairs the work's fonts before `drive-prep` converts it, as the
`extract-corpus` skill states. NEVER repair a filed PDF
whose corpus file has a body without telling the user the body was extracted
from the unrepaired text layer.

## Dispatch

| Rule | Holds |
| --- | --- |
| Stage 0 is per-PDF and independent | several `pdf-cleaner` dispatches MAY go in one message |
| Every PDF is two dispatches, and the second waits on the first | `pdf-bookmarker` runs only after `pdf-cleaner`'s report says the cover is final and the font repair is done; a `glyph-reader` dispatch sits between them when `scan` leaves a code unresolved; the dependency is per-PDF, and different PDFs' runs interleave freely |
| Each dispatch names its own PDF | a worker sees only its worker instructions and its prompt |
| Outside the `ingest` workflow, a long book MAY be bookmarked in ranges | dispatch `pdf-bookmarker` once per range, each prompt carrying the range, the checklist, the entries confirmed so far, and the path of its entries file. A range worker writes its entries file and NEVER calls `toc write`; the orchestrator passes every range's entries file, in page order, as one `--entries` each to one `toc write`, reads the diff, then runs the same with `--apply` |
| A `pdf-cleaner` report marked partial is a failed dispatch | the worker's turn cap stopped it before its report; dispatch `pdf-cleaner` again on that file once, and if the second report is partial too, stop and ask the user |
| Dispatch at most four `pdf-cleaner` workers in one message | every worker renders pages on the same machine; let the group land before the next |
| Clean ahead of Stage 1 | the inbox holds every cleaned file until Stage 1 files it: a group MAY clean while previously cleaned files are filed one at a time |

If a worker's report names something it stopped on, resolve it or ask the user
before dispatching the next step on that file.

## The ingest workflow

**The `ingest` workflow cleans each PDF of a batch through the three workers
and three `drive-*` subcommands, which carry no judgment.** Each subcommand
prints one JSON line whose `state` names the next step, and keeps its files
in the PDF's batch work directory, `ingest/<inbox stem>/` in the scratch
directory, reached as `ingest/by-key/<key>/`. `<key>` is the work key the
`ingest` skill states; outside a batch, it is the PDF's name. Each worker
returns a structured report, whose fields its worker instructions state.

| Step | Runs | `state` and next step |
| --- | --- | --- |
| `pdf-cleaner` dispatch | steps 1 to 5 of the procedure | `partial` true: dispatch again once, then set the PDF aside. `cover` `not-searched` on a book or a volume: dispatch again once, then set the PDF aside. `kind` `none`, or a non-empty `stopped_on`: set the PDF aside. Otherwise run `drive-fonts` |
| `drive-fonts <key>`, detached through `ingest.py drive-detach`, under the engine lock | steps 1 and 2 of the font repair: `scan`, once more on an unread sheet or an unresponsive Apple Vision, then `identify` into the work directory; if no code is unresolved, step 5 instead: `repair` and its `--apply`; if more than 30 codes are unresolved, neither | `glyphs`, with `groups`, its `count` and the `codes` and `answers` file names in the line's `dir`, in which `{n}` stands for the group's number, 1 to `count`: dispatch `glyph-reader` once per group, naming the group's `codes` listing and its `answers` path, then run `drive-learn`. `bookmark`: dispatch `pdf-bookmarker`; with `force_ocr` true, the font repair cannot settle the codes: run "Codes the font repair cannot settle", which a line carrying `pixel_pages`, the path of the work's `pixel-pages.json`, settles by its page listing |
| `drive-learn <key>` | steps 4 and 5 of the font repair: `learn-reader` and its `--apply` on the glyph reader's answers, then `repair` and its `--apply`; no repair when every code it leaves unresolved needs none | `bookmark`, with `notes` for the batch's one report: dispatch `pdf-bookmarker`; with `force_ocr` true, as `drive-fonts`. `unwritten`: a group listing has no answers file; dispatch `glyph-reader` on every group again once, then run `drive-learn` again; a second `unwritten` sets the PDF aside |
| `pdf-bookmarker` dispatch | step 6 of the procedure, in one dispatch | a dispatch that fails or stops before its report: dispatch again once. `outcome` `failed`, a volume's `outcome` `no-divisions`, a non-empty `stopped_on`, or a second dispatch with no report: set the PDF aside. Otherwise carry `unfound` into the batch's one report under the work, and run `drive-route` with the PDF's kind |
| `drive-route <key> --kind <kind>` | an article or a book: records in the work directory that Stage 0 is done, so a later batch starts the PDF at Stage 1. A volume: the completion table's volume row, `volume` and its `--apply`, then the `extract-chapters` skill's `contents` | `file`: run Stage 1. `aside`, for a volume, with the chapter list as its `question` |

**`drive-learn` runs one PDF at a time across the batch.** `learn-reader
--apply` replaces the whole identity table, so two runs at once lose an entry.

**`drive-learn` passes `--partial` only when every code the repair leaves
unresolved is one `learn-reader` lists under `needs_no_repair`.** A glyph the
worker left `unresolved`, an answer `learn-reader` lists under `set_aside`,
and a repair that leaves any other code unresolved each print `bookmark` with
`force_ocr` true, learning nothing and repairing nothing. Only the first
names the glyph reader's answers path in the note.

| `state` | Means | Do |
| --- | --- | --- |
| `aside` | a failure branch above says stop and ask the user about this PDF | set the PDF aside with the line's `question` |
| `halt` | `vision-unavailable`, a model the cache lacks, or an identity table that does not parse | stop the batch with the line's `question`: the failure recurs on every PDF |

**Stage 2 bookmarks a filed work it finds without an outline.** If the
`extract-corpus` skill's `drive-prep` prints `unbookmarked`, the work is
filed, its `type:` is neither `journalArticle` nor `bookSection`, and its PDF carries no
outline, or only page entries, entries `pdf-bookmarker` defines as naming a
page and no division. The workflow then runs step 6 of the procedure on the library PDF:

1. Dispatch `pdf-bookmarker` on the work file, whose `pdf` names the library
   PDF, as the kind the line's `kind` names, whose cover work is final:
   `book` for a `type:` of `book` or `thesis`, `article` for any other type,
   which the worker bookmarks from its section headings; if the line carries
   `pixels_only` true, the prompt says the text layer cannot be trusted. The
   outline is the authorized overwrite `AGENTS.md` §5 names, and no other
   write touches the filed PDF.
2. If the report's `outcome` is `kept`, `pruned`, or `built`, run `drive-prep`
   again.
3. If the `outcome` is `no-divisions`, the worker found no division: run
   `drive-prep --one-chapter`, which records in the work's state that the
   work is extracted as one chapter without an outline.
4. If the `outcome` is `failed`, `stopped_on` is not empty, or the dispatch
   stopped before its report twice, set the work aside. If `drive-prep` prints
   `unbookmarked` again, set the work aside.
