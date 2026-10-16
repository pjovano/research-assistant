---
name: file-pdfs
description: "Stage 1 — file one cleaned PDF from the inbox: create its Zotero record, let ZotMoov place the PDF, write its corpus file's frontmatter."
allowed-tools: Bash(~/.research-vault/venv/bin/python .claude/skills/file-pdfs/scripts/file.py:*), Agent
---

# file-pdfs (Stage 1)

**Stage 1 files one cleaned PDF.** Its input is the cleaned PDF in the inbox,
which Stage 0 rewrote in place. Its output is the Zotero record, the PDF
placed in the library under the name ZotMoov gives it, and the corpus file
in the derived corpus, carrying its frontmatter and its PDF link and no body
yet. In a batch, the `ingest` workflow runs this skill; outside a batch, the
orchestrator does. The `pdf-filer` worker records the Zotero record's
fields.

## Invariants

| Invariant | Consequence |
| --- | --- |
| Zotero owns the Zotero record and the citekey. | `name` and `citekey` predict Zotero's result; NEVER compute either by another rule. `citekey`, and `bib --set` with it, count as taken every citekey a corpus file, a draft card, or Better BibTeX holds. After the record is created, `file` reads the citekey Zotero assigned and records that key, so a Better BibTeX suffix (`smith2019a`) never becomes a second record. |
| Zotero's data directory lives outside the vault and NEVER in iCloud. | If it sits inside the vault or under iCloud, stop and ask the user before filing. |
| ZotMoov names and places the PDF. | NEVER rename or move a PDF into the library by hand. |
| The connector only creates. | Every field MUST be right at creation. Repair routes: "Repairing a filed record". |
| Stage 1 serializes on the single Zotero connector. | File one PDF at a time; NEVER two filing commands in one message. |
| On the primary, Zotero's Linked Attachment Base Directory MUST point at the library. | If it points elsewhere, Zotero stores an absolute path, which breaks once a secondary becomes the primary: stop and ask the user to set it before filing. |
| The `pdf-filer` worker runs on the model its worker instructions name in `model:`. | Its errors are silent and unrecoverable, so its behaviour NEVER changes under a model upgrade. NEVER dispatch it on another model, and NEVER override its model in the dispatch. |

## Definitions

**The draft card** is the file `<basename>.md` beside the PDF in the inbox.
It holds what the worker records before the record exists: the corpus
file's frontmatter fields as they will be written, plus three keys the
corpus file never carries — `zotero`, a mapping of native Zotero fields for
the record; `filed`, whether the record has been created; and `item_key`,
the Zotero item key the connector returned. `bib --set` writes
it; `file` consumes it.

**The corpus file** is `research vault/corpus/<basename>.md`, written by
`file` once the placed PDF is verified in the library. Stage 1 writes its
frontmatter and its first body line, the PDF link
`[<basename>.pdf](zotero://open-pdf/...)`; Stage 2 writes the body after
that line.

**The Stage 1 frontmatter** is `title`, `author` (a list of surnames), `year`,
`orig_year`, `type` (the Zotero `itemType`), `citekey`, `source_type` and
`source_role` (empty until Stage 4), `field` (an empty list until Stage 4),
`aliases`, `uncitable` when the record's `extra` carries the token the
`pdf-filer` worker instructions describe, and `amended_name` when `extra`
carries an `Amended name:` line.

**An opaque title** is a main title made of nothing but the names of
persons. The `pdf-filer` worker gives such a work a filename that says what
it treats: the full title where the title has a subtitle; otherwise **the
amended name**, `<main title> on <subject>`, the subject taken from the
volume's title, with the reason recorded in `amended_name`. `title` keeps the
printed title in both cases.

**The basename** is the filename ZotMoov gives the PDF, without `.pdf`. The
corpus file is keyed to it, so a wrong title is a wrong, permanent basename.

## Invariant: Zotero auto-sync off

**Zotero's auto-sync is always off; the user syncs Zotero by hand after a
session.** With auto-sync on, ZotMoov stops placing PDFs after roughly ten
filings and does not recover. NEVER ask the user to switch auto-sync on or
off. If filing shows the stall signature, apply "Stall signature".

**Stall signature.** The record files, the citekey resolves, and `doctor`
reports `zotero_online`, but the PDF stays in Zotero's `storage/<key>/` and
`file` reports `filed-unverified`. On the stall signature, stop and ask the
user to run ZotMoov's *Move to ZotMoov directory* on the record or restart
Zotero, then run `retry`. NEVER file into a stalled Zotero.

## Procedure

`file` takes one PDF's filename as it stands in the inbox. `probe`,
`opening`, `identify`, `bib`, `name`, `citekey`, and `refile` take that
filename, or the library basename once the PDF is filed. `doctor` and `status` take no
argument; `retry` takes none, or `--only "<pdf>"`. `relink` takes a library basename, or none for every corpus
file. `note` takes a library basename.

1. **Environment check.** Run it before a batch's first filing; MAY skip it
   for the batch's later PDFs:

   ```
   ~/.research-vault/venv/bin/python .claude/skills/file-pdfs/scripts/file.py doctor
   ```

   If it reports `zotero_online` false, stop and ask the user to start
   Zotero. NEVER file against a Zotero `doctor` has not passed.

   `doctor` and `status` also report `conflict_copies`: every sync conflict
   copy beside a corpus file or a library PDF. If the list is non-empty,
   iCloud forked a file: stop and ask the user to merge and delete the copy
   before the batch.

2. **Dispatch the `pdf-filer` worker** on the PDF. The worker runs the
   read-only commands (`probe`, `name`, `citekey`), runs the identifier pass first (`identify`,
   then `identify --write` once the proposal is confirmed against the PDF),
   reads the opening pages (`opening`), completes the Zotero record's fields
   on the draft card (`bib --set`), and stops before `file`. The worker prompt MUST name the PDF and MUST state: do
   not run `file`, `retry`, `refile`, or `relink`.

3. **Read the worker's report.** If it reports that it could not establish
   the title, the creators, or the year, stop and ask the user. Otherwise
   continue.

4. **Check the draft card** — writes nothing:

   ```
   ~/.research-vault/venv/bin/python .claude/skills/file-pdfs/scripts/file.py bib "<pdf>"
   ~/.research-vault/venv/bin/python .claude/skills/file-pdfs/scripts/file.py name "<pdf>"
   ```

   If `bib` or `name` exits non-zero, stop and ask the user, naming the
   error: the draft card cannot be checked.

   If `name` prints a title made of nothing but the names of persons and
   the worker's report does not name the title as opaque, return to step 2
   once, naming the opaque title in the prompt.

   If `missing_for_type` is non-empty, return to step 2 once, naming the
   missing fields in the prompt. If it is still non-empty after that second
   dispatch, stop and ask the user: the connector cannot add a field later.
   Otherwise continue.

5. **File it:**

   ```
   ~/.research-vault/venv/bin/python .claude/skills/file-pdfs/scripts/file.py file "<pdf>"
   ```

   `file` first files every draft card in the inbox not yet marked
   `filed: true`, whatever PDF was named, then creates this PDF's Zotero record through
   `/connector/saveItems`, posts the PDF's bytes through
   `/connector/saveAttachment`, polls for ZotMoov's placement, and on a
   verified placement writes the corpus file and deletes the draft card.
   ZotMoov moves the PDF out of the inbox, so no copy of it is left there.

   If `file` or `retry` exits naming a Better BibTeX failure, stop and ask
   the user: the duplicate check could not run, and a record filed past it
   can be a second copy of a held work.

   NEVER call `file` while a dispatched `pdf-filer` worker is still running:
   the resume pass files every unfiled draft card in the inbox, a draft card is
   written incrementally, and the connector cannot update what it creates.

   | `status` | Meaning | Do |
   | --- | --- | --- |
   | `filed` | record created, PDF placed, corpus file written | proceed to Stage 2 |
   | `filed-unverified` | record created, PDF not placed in time | run `retry`; if it reports `still-unverified`, apply "Stall signature". If the payload carries `placed_elsewhere`, ZotMoov placed a PDF under this citekey with that other name: the citekey collided with another work, or the prediction and ZotMoov's template disagree. Compare the two names and NEVER treat the filing as verified |
   | `zotero-offline` | nothing created; the draft card keeps the citekey | start Zotero, then run `retry` |
   | `connection-lost` | the connection dropped while the record was posted; whether Zotero created it is unknown | run `retry`: it asks Better BibTeX whether the record exists before creating one |
   | `filed-no-attachment` | record created; the PDF's bytes were not attached | attach the PDF to the record by hand in Zotero, then run `retry` |
   | `connector-refused` | Zotero is running and refused the record; nothing created | stop and ask the user: a retry repeats the refusal |
   | `duplicate` | the library, the corpus, or the talk transcripts already hold the work under the name ZotMoov would give it, in `held_as`; nothing created | stop and ask the user whether the copy is a second edition |
   | `duplicate-in-zotero` | Better BibTeX already holds, under the citekey in `held_as`, a record of the draft card's DOI; or, unless the work is a `bookSection`, a record that is not a chapter and carries its ISBN; or a record of this title whose first creator is the work's; nothing created | stop and ask the user whether this is a second edition or a re-download; file only once the Zotero record is deleted or reconciled |
   | `filed-note-collision` | record created and PDF placed, but a corpus file or a transcript of the placed name already existed; the corpus file is untouched and the draft card kept | stop and ask the user |
   | `already-filed` | a corpus file for this basename exists | nothing |
   | `note-changed-on-disk` | the note named in `path` changed on disk between its read and its write; nothing further was written | stop and ask the user: the Zotero record MAY already exist while the draft card does not record it |
   | `no-creator` | the record names no creator surname; nothing created; `message` says so | return to step 2, naming the missing creators in the prompt |
   | any other value | unspecified | stop and ask the user |

   `retry` reports one status per pending draft card:

   | `status` | Meaning | Do |
   | --- | --- | --- |
   | `retried-ok` | record created, PDF placed, corpus file written | proceed to Stage 2 |
   | `verified-on-retry` | the earlier record's PDF is now placed | proceed to Stage 2 |
   | `still-unverified` | record created, PDF still not placed | apply "Stall signature"; `placed_elsewhere` means what it means under `filed-unverified` |
   | `retried-unverified` | record created on this attempt, PDF not placed | apply "Stall signature" |
   | `filed-note-collision` | PDF placed, but a corpus file or a transcript of the placed name already existed; the corpus file is untouched and the draft card kept | stop and ask the user |
   | `retry-failed` | the connector refused; nothing created | stop and ask the user |
   | `retry-skipped-missing-file` | the draft card names a PDF in neither the inbox nor the library | stop and ask the user |
   | `already-filed` | a corpus file already holds the draft card's inbox name; nothing created | stop and ask the user |
   | `no-creator` | the draft card names no creator surname; nothing created | stop and ask the user |
   | `note-changed-on-disk` | the note named in `path` changed on disk between its read and its write; nothing further was written | stop and ask the user: the Zotero record MAY already exist while the draft card does not record it |
   | `zotero-still-offline` | Zotero is not running; the resume pass reports one such row per pending draft card | start Zotero, then run `retry` |
   | any other value | unspecified | stop and ask the user |

6. **Status** at any time:

   ```
   ~/.research-vault/venv/bin/python .claude/skills/file-pdfs/scripts/file.py status
   ```

**On completion** the corpus file exists with its frontmatter and its PDF
link, the PDF sits in the library under the corpus file's basename, and
nothing of the PDF remains in the inbox: neither the PDF nor its draft card.

## The ingest workflow

**The `ingest` workflow files each PDF of a batch through two `drive-*`
subcommands, which carry no judgment.** Each prints one JSON line whose
`state` names the next step. The workflow dispatches the `pdf-filer` worker
with a structured report, outside the Zotero lock, then runs `drive-card`,
then `drive-file` under the Zotero lock, one PDF at a time. `<key>` is the
work key the `ingest` skill states; outside a batch, it is the PDF's name.

| Step | Runs | `state` and next step |
| --- | --- | --- |
| `pdf-filer` dispatch | step 2; the report carries `citekey`, `title_opaque`, `unestablished`, and `uncertain` | if the dispatch fails or returns no report, dispatch the worker again once, and set the PDF aside if the second returns none; if `unestablished` is non-empty, set the PDF aside: step 3 applies; otherwise run `drive-card`, and carry `uncertain` into the batch's one report under the work |
| `drive-card <key>` | step 4: `bib` and `name`; it records in the batch work directory that Stage 0 is done, so a later batch carries the PDF on from Stage 1 | `card-ok`, with `name`'s main title as `title`: if the report's `title_opaque` is false, the `title-checker` worker judges whether `title` is an opaque title; if it is, dispatch the worker again once, naming the title; otherwise run `drive-file`. `redo-card`, with `missing`: dispatch the worker again, naming the missing fields, then run `drive-card`; a second `redo-card` prints `aside` |
| `drive-file <key>` | step 5: `file --only`, then `retry --only` where the status table says run `retry`; on `filed`, it lists the key under the basename, and rewrites the work file | `filed`, with `basename`: run Stage 2 on the key. `aside`: every status other than a filed status and a `halt` status, among them `already-filed`, `no-creator`, and `filed-no-attachment`; carry out the status row's own step after the batch. `halt`: `zotero-offline`, the stall signature, a Better BibTeX failure, or `connection-lost` on `file` and a failed `retry` after it |

`file "<pdf>" --only` files the named PDF alone, without the resume pass over
the other unfiled draft cards; `retry --only "<pdf>"` retries that PDF's
draft card alone. NEVER run `file` or `retry` without `--only` while the
workflow runs: the resume pass files another PDF's draft card while its
worker still writes it.

If a line's `state` is `aside`, set the PDF aside with the line's `question`.
If it is `halt`, stop the batch with the line's `question`: the failure
recurs on every PDF.

## `identify`

`identify` finds the identifiers a PDF carries (DOI, ISBN, arXiv ID) in its
metadata, its XMP, its first six and last three pages, and its filename;
resolves the first through the public metadata API for its kind; and prints
the **proposal**: the record normalized to the `pdf-filer` worker's rules,
with `missing_for_type`, the normalizations applied, and the flags raised.

```
~/.research-vault/venv/bin/python .claude/skills/file-pdfs/scripts/file.py identify "<pdf>"
~/.research-vault/venv/bin/python .claude/skills/file-pdfs/scripts/file.py identify "<pdf>" --write
```

Without `--write` it writes nothing. With `--write` it records the proposal's
fields on the draft card through `bib --set`'s path, refuses on
`filed: true`, leaves a differing recorded field untouched and lists it under
`conflicts`, and writes the `identified` key: the identifier, the service,
the fetch time, and the normalizations. `file` reads nothing from
`identified` and NEVER writes it into the corpus file. A network failure is
a `lookup-failed` status, and the identifiers found are still printed.
`identify` NEVER touches Zotero.

Crossref's polite pool wants a contact address: name it in `machine.json`
under `crossref_mailto`. If the key is absent, the lookup runs without one.

## `bib --set`

`bib --set FIELD=VALUE` edits the draft card. Repeat `--set` for several
fields; an empty value clears the field.

| Field | Goes to | Note |
| --- | --- | --- |
| `orig_year` | the corpus file's `orig_year` | drives the citekey and the record's `Original date:` line; MUST be set before `file` |
| `aliases` | the corpus file's `aliases` | the original-language title of a translated work |
| `creators` | `zotero.creators` | a JSON array of native creator objects |
| any other name | `zotero.<name>` | a native Zotero field name for the item type |

If the draft card records `filed: true`, `bib --set` refuses: the record
exists, and the connector cannot update it.

If `bib --set`, `identify --write`, or `relink --apply` prints `{"error": …,
"path": …}` and exits 1, the note at `path` changed on disk after the command
read it, and nothing more was written: run the command again once; if it
refuses again, stop and ask the user.

## Batching outside the ingest workflow

Only `file`, `retry`, `refile`, and `relink` write to Zotero; `citekey` and
`bib --set` read Better BibTeX, and exit with a Better BibTeX error while
Zotero is offline. Outside the `ingest` workflow, run a backlog in two
phases:

1. **The Zotero record's fields, in parallel.** Dispatch one `pdf-filer` worker
   per PDF in one message, each prompt as step 2 states.
2. **Filing, serialized, inline.** After every worker has reported, call
   `file "<pdf>" --only` once per PDF, one call at a time, from an explicit list of the
   basenames whose worker reported. NEVER derive the list from the inbox: a
   draft card is written incrementally, so its presence does not mean its
   worker has finished.

`file` takes one PDF: phase 2 calls it once per PDF from the reported list.
Give the filing loop a timeout of at least `ATTACH_SETTLE_SECONDS` (30 s)
per PDF.

## Writing the corpus file of a filed PDF

If a PDF sits in the library with no corpus file, `note` writes the corpus
file from the PDF's Zotero record. It finds the record through the
attachment path in Zotero's database, takes the citekey and the record's
fields from Better BibTeX, and writes the Stage 1 frontmatter and the PDF
link. Zotero's database is `zotero.sqlite` under `~/Zotero`; if a machine
keeps the data directory elsewhere, name it in `machine.json` under
`zotero_data_dir`.

```
~/.research-vault/venv/bin/python .claude/skills/file-pdfs/scripts/file.py note "<basename>"
~/.research-vault/venv/bin/python .claude/skills/file-pdfs/scripts/file.py note "<basename>" --apply
```

Without `--apply`, `note` prints the frontmatter it would write and writes
nothing. Read that output before running `--apply`. Zotero MUST be running:
`note` reads the citekey and the record through Better BibTeX.

| `status` | Meaning | Do |
| --- | --- | --- |
| `would-write` | read-only form: the record was found and its frontmatter printed | read it, then run `--apply` |
| `note-written` | the corpus file was written | proceed to Stage 2 |
| `already-filed` | a corpus file for this basename exists | nothing |
| `zotero-offline` | Zotero is not running | start Zotero, then run again |
| `no-record-attaches-pdf` | no Zotero record holds this PDF as an attachment | stop and ask the user |
| `held-as-transcript` | a transcript, named in `detail`, already holds the basename | stop and ask the user |
| `note-changed-on-disk` | the note named in `path` changed on disk between its read and its write; nothing further was written | stop and ask the user: the Zotero record MAY already exist while the draft card does not record it |
| `no-citekey` | the record has no Better BibTeX citekey; `detail` names the item key | stop and ask the user |
| `record-unreadable` | Better BibTeX exported no record, or no link, for the citekey in `detail` | stop and ask the user |
| `unknown-item-type` | the record's CSL type, named in `detail`, maps to no corpus-file `type:` | stop and ask the user |
| any other value | unspecified | stop and ask the user |

## Repairing a filed record

**Route 1 — Zotero's Run JavaScript console.** PREFER this route OVER every
other for a field change: it edits the record in place and leaves the
citekey, the attachment, and the basename untouched. The orchestrator cannot
run the console: generate the script and ask the user to run it. Resolve the
item key with `zotero.get_item_key(citekey)`; NEVER edit a record matched by
title: two works share a title, and the wrong record is edited silently.
`file` does search by title, to read back the citekey Zotero assigned and to
find a work Zotero already holds; it only reads.

```js
const item = await Zotero.Items.getByLibraryAndKeyAsync(Zotero.Libraries.userLibraryID, key);
item.setType(Zotero.ItemTypes.getID('journalArticle'));
item.setField('publicationTitle', '…');
item.setCreators([{creatorType:'author', firstName:'…', lastName:'…'}]);
await item.saveTx();
```

Rules for a generated script:

- Emit the values as a JSON array inside the script; retype nothing by hand.
- Write no backslash escapes into the JS; build newlines with
  `const NL = String.fromCharCode(10);`.
- Wrap every `setField` in try/catch and append a refused value to `extra`:
  Zotero throws on a field invalid for the item type.
- APPEND to `extra`, NEVER replace it: it carries the `Original date:` line,
  the `⚠ UNCITABLE-PDF` token, and the `Amended name:` line.
- Before sending, check that every JSON payload line parses and that the file
  contains no raw control character.
- NEVER force a citekey refresh: Better BibTeX keeps the key stable when the
  date changes, and the basename depends on it.
- If the change alters `title`, `orig_year`, or `aliases`, edit the corpus
  file's frontmatter to match by hand.

**Route 2 — by hand in Zotero.** Take this route only when the user declines
to run the Route 1 script. Mirror any change to `title`, `orig_year`, or
`aliases` in the corpus file's frontmatter.

**Route 3 — delete the stale record, then `refile`.** Use this route when the
basename or the attachment must change.

```
~/.research-vault/venv/bin/python .claude/skills/file-pdfs/scripts/file.py bib "<pdf>" --set ...
~/.research-vault/venv/bin/python .claude/skills/file-pdfs/scripts/file.py refile "<pdf>"
~/.research-vault/venv/bin/python .claude/skills/file-pdfs/scripts/file.py refile "<pdf>" --stale-item-deleted
```

**`refile` builds the Zotero record from the library PDF, the corpus file's
`orig_year` and `aliases`, and the draft card's `zotero` fields.** It holds
the PDF under `library/.refiling/` while ZotMoov places a copy under the
canonical name, rewrites the corpus file with its body and its hand-written
fields preserved — the classification, `commentary_on:`, `aliases`,
`amended_name`, and `uncitable`, the corpus file's value winning wherever
it holds one — and on failure restores the PDF to the library.

| Rule | Holds |
| --- | --- |
| every native field is recorded again with `bib --set` first | the corpus file holds none of them |
| `refile` refuses as incomplete, naming the missing fields, `title` and `creators` among them | record the named fields and run it again; NEVER pass `--allow-incomplete` without the user's instruction |
| without `--stale-item-deleted` | `refile` reports what it would file and changes nothing: deleting the stale record is the user's call, and refiling over a live record creates a duplicate |
| `note-changed-on-disk` | the note named in `path` changed on disk during `refile`; the PDF is put back, as the row's `note` says: stop and ask the user |
| `refile-renamed`, with the new name in `placed_as` | ZotMoov placed the refiled PDF under a different basename; no corpus file was written, the draft card is kept, and the corpus file and the bibliographies still carry the old basename: stop and ask the user |

## Repairing a PDF link

If a corpus file's first-line link no longer opens the PDF — the record was
refiled by hand, or the attachment was replaced — re-resolve it through the
connector. If Zotero is not running, `relink` refuses and writes nothing:
start Zotero and run it again.

```
~/.research-vault/venv/bin/python .claude/skills/file-pdfs/scripts/file.py relink
~/.research-vault/venv/bin/python .claude/skills/file-pdfs/scripts/file.py relink "<basename>.pdf"
~/.research-vault/venv/bin/python .claude/skills/file-pdfs/scripts/file.py relink --apply
```

Without `--apply`, `relink` reports each corpus file whose link would change
and writes nothing; read that report before running `--apply`. It resolves
the link from the corpus file's `citekey` alone; a corpus file with no
citekey or no attachment in Zotero, or whose lookup Better BibTeX failed
(`lookup-failed`), is listed and left as it is. It rewrites
the link line only.
