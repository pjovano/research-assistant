# Characterization suite

Control plane, not vault content. Pins the **current** behaviour of the
pipeline's pure functions so a refactor can be verified. Contract §5 runs the
affected test modules after every edit, and this test suite before every push
and in CI. Run the test suite from the repository:

    ~/.research-vault/venv/bin/python -m unittest discover -s tests -v

**Every test module runs alone.** The post-edit hook runs each affected test
module by name, with `tests/` alone on the search path. A test module MUST call
`LiveTree.activate()`, or import a helper that calls it, before it imports a
module of `lib/` or of a skill's `scripts/`.
`test_every_test_module_activates_the_search_path_before_importing_the_control_plane.py`
fails a test module that does not.

Stdlib `unittest` only: the suite adds no entry to `requirements.txt`.
Every test builds its own PDFs and notes in a temporary directory, through
`_vaults.py`, and points the code at them. NEVER read a library PDF in a
test: CI runs against an empty vault, so the test would skip there. A test
that pins a fix builds the defect class in a PDF of its own and is named for
the defect class (contract §5). NEVER write a test that writes to the inbox, the
library, the corpus, or the bibliographies.

## What it covers

The table names the suite's principal modules. A module named for the defect
class it pins states its own coverage and is not listed.

| File | Surface |
| --- | --- |
| `test_drafts_manuscript.py` | Edit drafts: a draft's pandoc citations read with their locators, in brackets, in the text, and in footnotes; the citekeys of the corpus files; the report of keys held and not held; a draft exported through `pandoc` to a `.docx` with its citations resolved and its bibliography, and to a PDF where typst is installed; a named citation style |
| `test_imports.py` | every facade, every `_` package, and every entry script imports; `vault.__all__` is pinned; the facade loads no token encoder |
| `test_vault_frontmatter.py` | frontmatter round-trip, LF enforcement, PDF-link upsert, a byte-order mark stripped, `parse_note`, `StoredNote` |
| `test_vault_citations.py` | the `source_type` and `source_role` vocabularies, `commentary_target`, citekeys |
| `test_providers.py` | the composition root: each port's adapter under each profile, `mac-local` the default and today's classes, an override replacing the profile's entry for its port, a missing key named, the API key read from the variable `key_env` names and never shown, each adapter loaded on first call and kept, `lib/_ports` importing the standard library alone, the report `providers.py` prints |
| `test_core_host_names_are_defined_in_the_core_alone.py` | no tracked file outside `vendor/` and `upgrade/` defines `Scheduler`, `Notifier`, `SystemReadings`, `Job`, `Notice`, or `Level` |
| `ports/test_*_contract.py` | one contract per port of `lib/_ports`, each a mixin an adapter's test case inherits, run here against the fakes of `_port_fakes.py`, `_rag_fakes.py`, and `_graph_fixtures.py`, and the full-text contract against the SQLite store besides |
| `test_vault_root_guard.py` | the vault is the directory `machine.json` names in `vault_dir`, `~/Documents` absent the key, and holds `research vault/`; a directory without it refuses to import; an unreadable `machine.json` stops the script with its path |
| `test_vault_locate.py` | `locate_pdf` keeps a bare path only inside a searched directory; NFC basenames over NFD filenames; the directory listings and conflict copies |
| `test_vault_markdown.py` | the shared heading, footnote-definition, and wikilink patterns; `BibliographySpan` |
| `test_vault_scratch.py` | `vault.py sweep` over a temporary scratch directory; the entries renamed at filing |
| `test_harness_hooks.py` | the harness hooks: the Bash guard's prompts, the Write guard, the command line, and the catch-all that blocks when the hook itself fails |
| `test_harness_hooks_checks_after_edit.py` | the checks after an edit: which files they cover, the audit linter's `works` check, the suite and the linter with their reports and time limits |
| `test_harness_hooks_from_the_shell.py` | each hook command of `settings.json` through a real shell under a fabricated home, and the project root it runs from |
| `test_harness_hooks_reach_the_vendored_core.py` | the health watcher hook run as the harness runs it, with only `lib/` on the module path, reaching the vendored core |
| `test_page_marker.py` | the page-marker grammar: parsing a marker line, finding markers inline, rendering one, slicing a body by its markers |
| `test_snapshots.py` | golden diffs over the frozen records: `vault` naming and citekeys, `zotero.build_item` |
| `test_references.py` | reference-zone location and extraction, entry parsing, held works from card frontmatter |
| `test_reference_parsing.py` | the citation parser's post-processing over hand-written span lists; the model loads only when it is cached |
| `test_graph_store.py`, `test_graph_signals.py`, `test_graph_neighbours.py`, `test_graph_clusters.py`, `test_graph_contexts.py` | the citation graph: the store's incremental sync over held edges and merged unheld works, the four signals and their weights, the neighbours with their shared references and tally, Louvain's determinism and the four findings, the three passage kinds with their folios |
| `test_bibliographies_glossing.py` | Stage 5: each listing glossed with its work's description, the plan over the touched bibliographies and those without an introduction, the bibliography introducer's listing with its works, groups, maps, and unsorted works, and the write of the introduction, the group notes, and the sorted works, with each refusal |
| `test_ingest_glosses.py` | Stage 5 in a batch: the copy before the plan, the plan step's numbered directories and listings, the answers written, a missing answers file and refused answers set aside |
| `test_bibliographies_reshaping.py` | the reshaping: a creation's file, lists, parent map, and moved works; a move's field, listings, and placement; each refusal writing nothing; the shaper's listing; the maps and listing helpers |
| `test_ingest_reshape.py` | the reshaping in a batch: the listing step's nothing and shape, the nominations file handed on, the answers applied, the touched file for the glosses, the refusals set aside |
| `test_ingest_cite.py` | Stage 3 in a batch: the per-work step's outbound, inbound, and graph sync calls and its halts; the citation sweep's whole sync |
| `test_reference_scoring.py` | the title similarity wrapper and the reference score: the surname gate, year agreement, pages, and the two bands |
| `test_rag_*.py` | the search stores: chunking, the full-text store, the embedding client, the reranker client with its startup probe, sync refusing a changed embedding model, hybrid search with its reranker note and staleness cache, and the heading tree over a fixture body, every network client faked |
| `test_pagetext.py` | `normalize` and the offset-keeping `NormalizedText` behind it, `assess` over a fake page classifier, page access through `PdfPages` over a built book whose every line opens on a tag unique to it, printed folios from its page labels, the page cache with its labels, quote finding on one page and across a page break |
| `test_pagetext_renders.py` | page renders to the scratch directory |
| `test_verify.py` | Answer questions: `verify` over a temporary library PDF and corpus file: the deep link at the hit's file page, the folio from the page marker with the text-layer fallback, an exact hit before a near match, `AMBIGUOUS` with its exit code, a quotation across a page break, `locate` with its limit and its use of the quote cache, the two reasons a link is absent; `quality` reporting a sparse text layer; the CLI on a missing PDF |
| `test_verify_exit_codes.py` | Answer questions: each outcome of `verify.py` under its own exit code, 0 verified, 1 not verified, 2 a usage error, 3 a poor text layer, 4 a failure |
| `test_health_*.py` | the health watcher: the pressure and thermal detectors on each side of their thresholds; the cooldown, the retention, a journal line cut short, the desktop and Reminders notifiers' title and list, the workload labels, the core's levels kept in the journal's spellings, the report; the launch agent installed, refreshed, or left alone by the hook before a pipeline command; the launch agent byte for byte as the former code wrote it; `install` and `uninstall` through the scheduler |
| `test_surya_servers.py` | the model servers' process handling, the idle reaper, and `surya_cache_dir` |
| `test_font_repair.py` | Stage 0: CMap parsing and regeneration, the character a glyph name names |
| `test_font_repair_identities.py` | Stage 0: the identity table, `fonts learn`, the resolver, and the code and name key spaces kept apart |
| `test_font_repair_flagged_codes.py` | Stage 0: the flagged codes, glyph names beside or without a ToUnicode table, codes emitted as characters, the font status rows |
| `test_font_repair_plan.py` | Stage 0: the repair plan: confirmed codes, the repair records, overrides reaching every subset of a family, retired characters a sibling object still emits |
| `test_font_repair_of_glyphs_a_tounicode_map_reads_as_dingbats.py` | Stage 0: the scan, identification, and in-place repair over a built PDF whose ToUnicode maps give glyph names the Dingbats characters another font's glyph list assigns them, two objects of one family setting different glyphs at one code, beside a font no identity resolves |
| `test_font_scan.py` | Stage 0: `fonts scan` over given records, and over the whole library without conflict copies or volumes |
| `test_font_pixels.py` | Stage 0: the pixel check, the line index, the OCR text conversion, the alignment and its verdicts, the cache with a lone surrogate, the Vision framework loaded lazily |
| `test_font_rows.py`, `test_font_unknown_unicode.py` | Stage 0: font rows and glyphs the reader cannot name |
| `test_annotate.py` | the marker grammar and OCR-damaged digits, marker debris on a word, edition labels, notes and the note ledger, tags, the annotation and revision specs with colour by name, the palette, `WordSpan`, a PDF outside the library refused, the CLI's error exits |
| `test_annotate_anchors.py` | over built books: the inline A/B and Akademie marker index and its strategies, a span crossing a two-up gutter refused, a cross-page span kept between the running head and the footnotes |
| `test_annotate_writing.py` | over a temporary copy of a built book: highlights written, merged, and read back with author and tag; cross-page pairs written, listed as one, and revised together; hand-made pairs; one quad per line; the revision dry run, its four changes, and its atomic write |
| `test_clean_in_place.py` | Stage 0: in-place de-annotation through a temporary file, PDF location order, the plans of `volume`, `add-cover`, and `drop-page` and their `--apply`, `drop-page` counting from 1, `toc write` on an article, the repair branch, geometry commands confined to the inbox, `plan --all` without conflict copies, the article threshold shared with Stage 1 |
| `test_toc_suggest.py` | Stage 0: `toc fonts` and `toc suggest` over a PDF built with a body font and two heading fonts; `--out` resolved under the scratch directory |
| `test_file_notes.py` | Stage 1: the `uncitable:` field from Zotero's `extra`, the `Original date:` placement, draft-card placement in the inbox, filing completion keeping hand-written fields and carrying the scratch entries, the connector statuses, the note-collision guard, the Zotero record read back through CSL for `note`, the database snapshot behind the WAL, citekey allocation reading frontmatter only, `doctor` and `status` naming conflict copies |
| `test_file_filing.py` | Stage 1: the connector's item key and its bare item, the citekey Better BibTeX assigns, awaited, and recorded before the poll |
| `test_file_filing_placement.py` | Stage 1: library membership, placement verified against the predicted name, a placement under another name reported, the duplicate guard, a verified filing reported `filed` |
| `test_file_filing_held_works.py` | Stage 1: a work Zotero already holds, by DOI, ISBN, or title and creator; a different work sharing a title or a book; a refused search never read as not held |
| `test_file_filing_retry.py` | Stage 1: `retry` offline, against a held work, and awaiting its own record's placement; `file` resuming only unfiled draft cards |
| `test_file_filing_refile.py` | Stage 1: `refile` holding the PDF under `library/.refiling/`, and a verified refile completing |
| `test_file_identify.py` | Stage 1: the identifier patterns and checksums, the finder over XMP, page text, and the filename, chapter-DOI evidence, language-aware Title Case, the record normalizer with the spaced-dash subtitle rule, the resolvers through an injected fetcher, `identify --write` and its refusals |
| `test_extract_guards.py` | Stage 2: refusal to replace a body without `--replace`; the frontmatter requirement; the scope `extract` requires and the scope points it resolves; page-check routing of transcribed and text-less pages; the idle reaper; the readings-file guards; page ranges |
| `test_extract_review.py` | Stage 2: the extraction record through the frontmatter and back; the trial in the scratch directory with its report; the review listing's page statuses and its collected notes, apart from the last page's text; `accept` writing the body, the record, and `extraction_reviewed:`, refusing a different body without `--replace`; the regression check's three states and its diff; `extract --trial` beside an existing body, `probe`'s review state, `review-status` |
| `test_extract_review_pages.py` | Stage 2: the pages the review listing names: the listing of a work within the cap unchanged, the cap of 40 pages, the heading pages capped at their share with every level-1 heading kept, the reported pages and the pages beside an excluded span before the even sample of kept pages, one page inside each excluded span |
| `test_extract_structure.py` | Stage 2: the page assembler, transcribed and omitted pages, heading scope, abstracts |
| `test_extract_folios.py` | Stage 2: folios from furniture and labels through the shared resolver |
| `test_extract_folio_signals.py` | Stage 2: the three folio signals in PDFs of their own: a page label where no folio prints, roman labels kept roman in the marker, a label tree contradicted by the printed folios and logged, the text layer's edge lines as the fallback, the label normalizer |
| `test_extract_regress_in_parallel.py` | Stage 2: the regression check run in processes reporting what a serial run reports, in the order the works were given, each changed work writing its own diff; a work the cache does not hold rebuilt after the processes, in its place; a cache-only conversion refusing the engine and reading the cache |
| `test_extract_scope_labels.py` | Stage 2: the scope listing's pre-labelled runs from the cached engine output, a contents page, a blank run, a bibliography run, their edges among the pages to judge, `null` before conversion; `convert` filling the cache through a fake engine |
| `test_extract_notation_blocks.py` | Stage 2: the per-page counts of the engine's `Equation` and `TextInlineMath` blocks the report carries |
| `test_extract_page_labels.py` | Stage 2: `labels` planning one range per run of folios, the read-only form writing nothing, `--apply` writing the tree read back and re-keying the engine cache, refusals on `uncitable:` and on a missing body, roman numerals |
| `test_extract_checks.py` | Stage 2: the page checks |
| `test_extract_writer.py` | Stage 2: HTML to Markdown, the note writer, bracketed labels |
| `test_extract_policy.py` | Stage 2: the section policy |
| `test_extract_lists.py` | Stage 2: hanging-indent lists |
| `test_extract_footnotes.py`, `test_extract_blocks.py` | Stage 2: footnote pairing and the document blocks |
| `test_extract_layer_marks.py` | Stage 2: combining marks, soft hyphens, and a note mark set on its own line, each in a PDF of its own |
| `test_extract_furniture.py` | Stage 2: a running head merged into the text below it, and a one-off footer inside the text |
| `test_extract_twins.py` | Stage 2: a region the engine reads twice, as a heading and as text |
| `test_extract_empty_blocks_straddling_read_blocks.py` | Stage 2: an empty block lying within the read blocks it overlaps, and the line it straddles written once, in a PDF of its own |
| `test_extract_withheld.py` | Stage 2: the marks of footnotes and endnotes the scope excludes |
| `test_extract_scans.py` | Stage 2: a text layer laid invisibly under the page images, and `probe` calling its work scanned |
| `test_extract_scans_with_a_visible_line_on_a_strip_the_page_image_leaves_bare.py` | Stage 2: a text layer laid invisibly under a page image that leaves a strip at the foot bare, with a visible line on the strip, not drawn and its work called scanned; visible text a later image covers one line of, drawn; in PDFs of their own |
| `test_extract_notation.py`, `test_extract_equations.py` | Stage 2: notation runs, placeholders, statement labels, the engine's own math |
| `test_extract_headings.py` | Stage 2: heading candidates against running heads, titles, and fragments; outline headings placed by position and written once |
| `test_extract_conversion.py`, `test_extract_indents.py`, `test_extract_margins.py`, `test_extract_strays.py` | Stage 2: the conversion plan, indents, margins, stray lines |
| `test_engine_reader.py` | Stage 2: the engine reader with only the engine packages faked |
| `test_engine_guard.py` | the engine guard: a request the model servers never answer fails within the silence limit, the model servers are stopped, the next request reaches a fresh one; a batch whose model servers keep writing their logs runs past the limit |
| `test_notation.py` | the shared notation code: notation placeholders, the Unicode-to-math-LaTeX table round trip, math-font detection, prose-only verification, word hyphens |
| `test_math_font_measure.py` | the math-font judgment by measure, over a PDF built with a prose font and a font set one glyph per span: each of the four thresholds pinned on both sides — the span count, the single-span share, the letter share, the share of the work |
| `test_accents.py` | accent folding |
| `test_cite_links.py` | Stage 4: wikilinks on bibliography entries and footnotes under the scored rule, each entry scored once; a linked line revisited by its alias; `]]` escaped; a later work and the citing work itself never linked; `to_confirm` left alone by `apply` |
| `test_cite_links_settles_a_middle_band_match_by_its_recorded_verdict.py` | Stage 3: a scored match the verdicts record settles is never reported again, a confirmed one linked and a rejected one never linked; `settle` over a score band and over a verdicts file, in both forms, refused while a run holds the run lock |
| `test_citation_graph.py` | the citation graph over a fixture corpus of three notes: `cites` and `cited_by` from the wikilinks, with the folio of each linking line |
| `test_cite_links_scores_an_entry_opening_with_its_year_under_the_author_above.py` | Stage 3: an entry that drops its repeated author without dashes, opening with its year bare, in parentheses, or after `ed.`, scored under the author above; a numbered entry never read so |
| `test_bibliographies.py` | Stage 3: the `## Maps` listings, the tree and its ancestors, the graph checks, bibliographies in subfolders, corpus lookup, section lines |
| `test_bibliographies_placement.py` | Stage 3: `place` on a topic bibliography, an author bibliography, and a transcript, leaving every other line byte for byte; a list of works carried twice refused |
| `test_bibliographies_diagnostics.py` | Stage 3: `check` with its conflict-copy, listing, and author groups, and the report |
| `test_bibliographies_opening.py` | Stage 3: `opening` of a transcript, and the current classification it reports |
| `test_drive_work.py` | the ingest workflow: the batch work directory, its state, and the backfill queue addressed by index or by basename |
| `test_drive_steps_run_no_guarded_command.py` | the ingest workflow: no `drive-*` module names a guarded command but the one the contract authorizes |
| `test_clean_drive.py` | the ingest workflow, Stage 0: `drive-fonts`, `drive-learn` with the codes left as they are, `drive-route`, and the halts |
| `test_file_drive.py` | the ingest workflow, Stage 1: `drive-card` and `drive-file`, their halts and set-aside statuses |
| `test_extract_backfill_driver.py`, `test_extract_drive_addressing.py` | the ingest workflow, Stage 2: the scope settlement, the trial's verification, the review routing, the halts, the detached engine steps, the queue addressed by index or by basename |
| `test_bibliographies_drive.py` | the ingest workflow, Stage 3: `drive-classify`, its answers, the write undone on a refused placement, an unplaced work, the halt on a conflict copy |
| `test_ingest_preflight.py` | the ingest workflow: `preflight` and each machine check |
| `test_ingest_batch.py` | the ingest workflow: `drive-batch`'s listing of inbox PDFs and filed works, each at the stage it reached |
| `test_ingest_batch_lists_the_pages_of_each_work_bound_for_the_engine.py` | the ingest workflow: the page count `drive-batch` lists for each work bound for the engine, from the inbox or the library, none for a missing or unreadable PDF |
| `test_ingest_detach.py` | the ingest workflow: `drive-detach` and `drive-wait`, a command's last JSON line, and a detached rebuild that still asks for permission |
| `test_ingest_tail.py` | the ingest workflow: `drive-check`, `drive-cite`, and `drive-index` with their questions, halts, and rebuild |
| `test_ingest_readings_checking_off_the_wanted_works_a_batch_placed.py` | the ingest workflow: `drive-readings` moving a wanted entry of a project reading list under held once its work is placed on a bibliography, in every project reading list that wants it; a held work placed on no bibliography, or with unparsable frontmatter, left wanted; a note of the folder that is no project reading list left as it is |
| `test_ingest_workflow_checking_off_the_project_reading_lists.py` | the ingest workflow: the tail running `drive-readings`, carrying the entries checked off, and asking the question of a step set aside |
| `test_ingest_progress.py` | the ingest workflow: `progress` by stage with the machine's health, and the selection `drive-batch` records |
| `test_volume_guards.py` | Extract chapters: `contents` and `extract` refuse a volume with no outline, `list` marks the outline absent or present; front matter, the index, and the collected apparatus are not chapters, and a chapter runs to the next opening at its level; a collected bibliography or endnotes is found by its heading and `Notes on Contributors` is not; `extract` appends the apparatus unless `--no-apparatus`, refuses a destination in the inbox, a range past the end, and a malformed range; an outline entry before page 1 is dropped |
| `test_board.py` | Manage projects, the board: a compressed drawing decompressed; a board file read and written with its Markdown side, its state, and its plugin keys kept; a card and an arrow drawn; a board's cards, relations, and free points read; `sync` carrying a card into a note's `projects:` and back, an arrow into a note's relation and back, each in both directions, without moving a card; an old project file upgraded; `card`; the commands |
| `test_notes.py` | Take notes: a claims block reworded and explicated in place; a claim, an explication, and a task written into a note, the first two with the review mark; a reference written from a verified quotation, last or after another; a quotation confirmed, refused, or ambiguous in its PDF, found once in a transcript under its time marker, and cited by chapter and section for an uncitable work; the commands of `notes.py` |
| `test_notes_highlights.py` | Take notes, the highlights, over a PDF the tests build: a quotation's word span located on its page, through case, punctuation, and a word hyphenated over a line break, and over a page break; several tags on one annotation; a reference read back from its block; the colour a topic takes within one PDF; a note's entry retagged beside another commentator's; `highlight` writing, merging, retagging, and reporting a quotation it does not locate |
| `test_projects.py` | Manage projects: a project file's status, parents, children, and headings, lines put first and last, links read back, a link listed once; a frontmatter link written as a single value; draft names whole and per section, a draft owned by the longest project name it opens with; parents and children read from the frontmatter, a one-sided link reported; `new`, `link`, `cut`, `publish`, `add`, and `status` over a temporary `writing/`, each plan writing nothing and each refusal; the CLI's `tree`, `note`, `section`, `place`, and `outline` |
| `test_reading_list.py` | Manage projects, the reading list: a wanted entry read as its author, year, title, and reason, and matched to the basename the library holds it under; an entry added under its status; the wanted entries the library now holds reported, and moved to held on a refresh; the list written into `bibliographies/4 reading lists/`; `reading` and `readings` |
| `test_projects_conversion.py` | Manage projects, the conversions, through `pandoc` over Word files the tests build: `import` writing the next version with its footnotes, headings, and block quotations, listed under `## Drafts`, the Word file left in a temporary inbox; `discard` handing the Word file to the Trash; `export` leaving out the frontmatter, Obsidian comments, and embeds, each export style's font, spacing, margins, and page numbers; each plan writing nothing and each refusal; a machine without `pandoc` |
| `test_discover_unheld_over_a_citing_set.py` | Discover: `unheld` over a citing set of many entries, where entries sharing no surname are never compared and titles under different first authors are never measured for similarity; citing works that print one reference list in common counted once, in `unheld`, under `--min-citing`, and in `merge`'s local citations, with one case on each side of the common-entries minimum |
| `test_discover.py` | Discover: `unheld` over a temporary corpus file and PDF reference zone, held-work exclusion, locators, two editions of one work merged, `--min-citing`; `RecordMatch` and `CitationMatch` rules; `merge` through the CLI from stdin and from `--unheld` and `--known` files: candidate deduplication with obtain links and truncated titles, held marking, local citations, ordering, unreachable sources, known items no candidate names |
| `test_vault_audit.py` | Vault Maintenance: the control-plane groups over a temporary repository; the audit set before and after an acceptance; the baseline over a temporary file — new, changed, removed, accepted with an injected date; the Clean Code measures over hand-written sources; instruction pointers over a temporary root with an injected today — a missing path, a present path, a vault path, a home path, a placeholder, a bare root file, a future date, a past date; named works — a basename in a rule and in a string constant, the basename pattern with placeholders; related files by reference form; the CLI's help |

Not reachable here: the Zotero connector, ZotMoov attachment polling, the
conversion engine, and the models behind the search stores.

## Fixtures and goldens

`fixtures/records.json` is a frozen copy of 479 draft-card and bib pairs.
`fixtures/goldens/` pins the output of the pure functions over them:
`vault_naming.json` and `zotero_build_item.json` map over every record;
`vault_naming_edge_cases.json` is built from hand-written inputs.

    ~/.research-vault/venv/bin/python tests/capture_goldens.py
    ~/.research-vault/venv/bin/python tests/capture_goldens.py --apply

**`capture_goldens.py` is dry-run by default, like every writing script in the
vault (contract §5).** Without `--apply` it writes nothing: it reports whether
each golden still matches and exits non-zero on a difference. It rejects
unknown arguments: NEVER add a flag that could write on a typo.

## Operating rule — updating a golden is a deliberate act

These tests pin current behaviour **including current bugs**. The suite detects
*change*, not *incorrectness*.

- A failure after a refactor is a **regression**. Revert it.
- A failure after an intentional fix means the expectation moves **as part of
  that fix**, in the same change: rename the test so its name states the
  corrected behaviour. The vault's code standard forbids comments.
- NEVER regenerate goldens in bulk to make the suite go green. Before accepting
  a golden diff, verify it is purely additive: new keys only, no key removed,
  no existing value changed. If an existing record's entry moved, a behaviour
  change is hiding inside the data update: stop and explain it on its own
  terms.
