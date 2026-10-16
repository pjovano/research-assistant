# Glossary — Research Vault

The glossary is the vault's Vocabulary rows and the vault's rules on
instruction text, which `clean-prose` reads after its own text.

## Domain content

**The vault's domain content is research content:** derived research notes,
the substance of a research answer, or the user's own drafts.

## Vocabulary

**This table extends the Vocabulary of `clean-prose` §5**, and §5's rules
bind every row.

| Term | Means | Banned synonyms |
| --- | --- | --- |
| bibliography | one topic map | topic, topic note |
| bibliographies | the directory holding the bibliographies | topics |
| retrieval layer | the derived corpus, the transcripts, and the bibliographies | summary layer, tier 1, index cards, source index |
| printed folio | the page number printed on the page | printed page number |
| file page | a page's ordinal position in the PDF file | PDF page number, PDF page index |
| library | the directory holding the corpus PDFs | — |
| vault | the directory `machine.json` names in `vault_dir`, `~/Documents` absent the key; holds `library/` and `research vault/` | project, research folder, workspace |
| Obsidian vault | `research vault/`, the directory holding every note | notes folder, notebook |
| Zotero record | the Zotero item that identifies one work; Zotero's own field names such as `itemType` stay as written | record (alone), entry, metadata, Zotero item |
| derived corpus | `research vault/corpus/`, the directory of corpus files, one per PDF, each in the directory itself and never in its subfolder `talk transcripts/` | corpus text, text layer, extracted text, source index |
| search stores | the primary's embeddings and full-text index, never synced | search index, vector store, embeddings (alone) |
| control plane | `~/Developer/research-assistant`, the repository: the contract, skills, worker instructions, and code | config, tooling, project |
| primary | the one machine that holds the control plane and runs every operation, written "the primary"; the `source_role` value `primary` is another term | main machine, home machine, always-on machine, master |
| secondary | any machine other than the primary, which holds the vault through iCloud and runs no operation, written "a secondary"; the `source_role` value `secondary` is another term | laptop (for a secondary), client machine, remote machine, second machine |
| adapter | the code `lib/providers.py` chooses for one key of `providers` in `machine.json`, by that key's `adapter` field, from the adapters this version provides | backend, driver, plugin, implementation (for an adapter) |
| `Defect-class:` trailer | the git trailer `Defect-class: <the defect class>` in the last paragraph of the message of a commit that fixes a defect | defect line, fix tag, defect note |
| `Change-class:` trailer | the git trailer `Change-class: refactor — <what>` or `Change-class: feature — <what>` in the last paragraph of the message of a commit that fixes no defect | change line, change tag, kind trailer |
| inbox | `~/Desktop/inbox/`, new PDFs awaiting ingest and Word files awaiting import | drop folder, queue |
| batch | the inbox's contents when ingest starts, each filed work an earlier batch left short of Stage 4, and each corpus file whose body is written and whose classification is not | run, ingest set, pass |
| set-aside PDF | a PDF of a batch whose stage reached `stop and ask the user`: left as it is, its question kept for the batch's one report | held PDF, skipped PDF, blocked PDF, parked PDF |
| halt | the `state` a `drive-*` step prints when its failure would recur on every PDF of the batch; the batch starts no further step | abort, crash, stop (for the state) |
| paused PDF | a PDF of a batch a halt stopped before its next step, which the next batch carries on | stalled PDF, interrupted PDF, set-aside PDF (for a paused one) |
| ingest workflow | `.claude/workflows/ingest.js`, which runs a batch, or a backfill from Stage 2 | pipeline, batch script, stage2 workflow |
| resolve-tasks workflow | `.claude/workflows/resolve-tasks.js`, which resolves the chosen tasks of the atomic notes: a note researcher per further note, then a note reviewer per reviewed note | note pipeline, task runner, notes workflow |
| further note | the atomic note a task names, which resolving the task creates and researches | child note, branch note, new note (for a further note) |
| stub note | an atomic note the user wrote with a title and a claim and no reference, which no chosen task names; the `resolve-tasks` workflow researches it | draft note, empty note, seed note |
| comment kind | one of `claim`, `dispute`, `pointer`: what a reference's comment does for a reader of the page, which gives its highlight's colour | comment type, note type, annotation category |
| dispute comment | a comment whose `Contra:` lines point to a held work's reading contrary to the reading the passage states or a `Cf.` line gives; its highlight is orange | contested comment, debate note, disagreement flag |
| batch update | the one message the orchestrator writes every `batch_update_minutes` while a batch runs: the works done and remaining by stage, and the machine's health over the interval | status update, progress ping, heartbeat |
| relay | the `relay` worker, one dispatch per `drive-*` step or other script step of the ingest workflow, that runs one command and returns its last line | runner, proxy, relay agent |
| run lock | `ingest-run.json` in the scratch directory, which `ingest.py drive-batch` takes and `drive-release` releases, so that one ingest workflow run at a time carries a batch | ingest lock, batch lock, mutex |
| session process | the nearest ancestor process of a command that is not a shell: the session that dispatched the relay, recorded as the run lock's holder | parent process (for the holder), owner |
| detached step | a command `ingest.py drive-detach` starts in the background under a key, whose JSON line `ingest.py drive-wait` collects | background job, async step |
| bibliographies check | `bibliographies.py check --json`, which `ingest.py drive-check` runs once per batch beside the citation sweep | check (for the bibliographies check), tree check |
| citation sweep | `ingest.py drive-cite` without a key: Stage 3 over every corpus file, then `graph.py sync` whole, once per batch after every work has stopped | full cite, tail cite, link pass |
| `drive-*` step | one subcommand of a stage's script that runs the stage's deterministic steps between two dispatches and prints one JSON line naming the next step | driver call, step script |
| batch work directory | `ingest/<basename>/` in the scratch directory, where the `drive-*` steps keep one PDF's files during a batch, keyed by its inbox name until Stage 1 files it | ingest folder, work folder |
| work key | the number `ingest.py drive-batch` lists a work under, which every `drive-*` step of the run takes as its work argument, and under which `by-key/` links the work's batch work directory | work index, work number, slot |
| work file | `work.json` in `ingest/by-key/<key>/`, naming the work's `pdf` and `basename` for a worker | manifest, sidecar (for the work file) |
| work classifier | the `work-classifier` worker, one dispatch per work, that writes its classification and the bibliographies it belongs to to an answers file | classifier (alone), placer |
| answers file | the JSON a worker writes for a `drive-*` step to read: the glyph reader's answers, or the work classifier's `classify-answers.json` | output file, result file |
| title checker | the `title-checker` worker, one dispatch per checked draft card whose main title the filer did not mark opaque, that judges whether the title is an opaque title | opaque-title agent, title judge |
| subset-hashed family | a font family whose name ends in six or more hexadecimal digits, one a numeral, before an optional style suffix | hashed font, unique font |
| proposal | the resolved record `identify` prints, normalized to the worker's rules, for the worker to confirm against the PDF | candidate record, lookup result, suggestion |
| draft card | the `<basename>.md` beside a PDF in the inbox, holding what Stage 1 records before the Zotero record exists | sidecar, side-store, stub card, staging card |
| Pass A / Pass B | Stage 2's conversion from the text layer / from pixels, whole-work, per sample unit of a scan, or per chapter | normal mode, OCR mode |
| layer sample | `extract.py layer-sample`'s measure of a scan's text layer against the engine's pixel reading of its sample pages, which settles the sample units read from the layer and those read from pixels | OCR check, layer test, layer audit |
| sample unit | a run of whole level-1 chapters, at least 20 pages long, that the layer sample reads from the layer or from pixels whole | sample chapter, block, segment (for a unit) |
| sample page | a file page of a sample unit that the layer sample reads from pixels to measure the text layer, and never writes | probe page, test page |
| agreement | the share of a sample page's pixel-read words, in order, that its text layer matches | accuracy, match rate, overlap (for the agreement) |
| scratch directory | `vault.SCRATCH_DIR`, a script's working directory for renders and drafts | temp dir, scratch space |
| session scratchpad | the session's own directory outside the vault, where a document for the user is written | scratchpad (for the scratch directory), temp folder |
| edited volume | a work whose contents are separately titled pieces cited on their own, held in `library/volumes/`, whether its pieces are by different authors or by one; also "volume" | anthology, collection, book (for a volume) |
| collected apparatus | a volume's own bibliography or endnotes, printed once for the whole volume rather than per chapter, and appended to every chapter cut from it | back matter, end matter |
| outline | a PDF's bookmark structure | bookmark tree, bookmarks, TOC |
| printed table of contents | the contents pages the work prints | contents page, TOC |
| corpus file | one note of the derived corpus, `research vault/corpus/<basename>.md`: the frontmatter Stage 1 writes, the body Stage 2 writes | corpus text file, extraction, text file, index card, card, note (for a corpus file) |
| page marker | the Obsidian comment `%% p. <folio> (file p. <N>) %%`, or `%% file p. <N> %%`, that Stage 2 writes where a page begins | page map, page break, page tag, sidecar |
| section policy | the rule by which Stage 2 drops the scope's excluded spans from the body, and nothing else | exclusion list, filter |
| scope | what Stage 2 leaves out of a work's body as carrying nothing of the work's content: its excluded spans, passed to `extract` as `--exclude` or `--exclude-nothing` and recorded in the extraction record | omissions, apparatus list, scope record |
| excluded span | one stretch the scope names, from a start point up to a resume point | excluded section, omitted section, dropped section, exclusion range |
| scope point | the start or resume point of an excluded span: `end`, `<file page>`, or `<file page>: <opening words of one line>` | anchor |
| scope listing | the JSON `extract.py scope` prints: the work, its outline sections, and each page to judge with its render and its text-layer lines | section list, outline dump |
| section scoper | the `section-scoper` worker, one dispatch per part of a scope listing, that returns every stretch of the pages to judge that carries nothing of the work's content as an excluded span | scoper (alone), apparatus judge |
| trial | a corpus file's body as `extract --trial` writes it into the scratch directory, with the corpus file's frontmatter and the extraction record, before the review | candidate (for a trial), draft body, provisional body, staging copy |
| extraction record | what the scripts keep about how a body was built: its scope, its conversion flags, its `mode`, its `reviewed` date, and its corrections; a trial carries the first three in its frontmatter, and `accept` moves the record into the extraction records file | scope record, build record |
| cleanup | the text-only pass that rearranges a trial's or a reviewed body's words into a readable layout: the layout corrector over the pages a script doubts, then `extract.py correct`; a batch runs it when passed `cleanup`, and the user names a reviewed work for it | edit pass, cleanup pass, correction pass |
| correction | one rearrangement the cleanup makes, by one of eight ops, that changes no letter but the furniture it drops and the text-layer lines it restores | edit, fix (for a correction), rewrite |
| layout corrector | the `layout-corrector` worker, one dispatch per part of a correction listing, that writes the corrections its pages call for to a corrections file | editor, corrector (alone), fixer (for the worker) |
| correction listing | the JSON `extract.py correction-listing` prints: the work, the pages file and the text-layer lines file, the outline headings, the scope, each page the cleanup reads with its flags and its lines, and the notes those pages cite | edit listing, page listing |
| corrections file | the JSON a layout corrector writes, the pages it read and its corrections; and the trial's `<basename>.corrections.json`, the corrections applied to it | edits file, verdicts file (for a corrections file) |
| extraction records file | `library/extraction-records.json`, one extraction record per work under its basename | scope file, record store, sidecar |
| reviewed work | a work whose extraction record carries a `reviewed` date, the date `accept` wrote its body | accepted work, done work, finished work |
| reviewed sweep | `vault.py sweep --reviewed --apply`, which `drive-release` runs once per batch: each reviewed work's page renders and font repair caches deleted from the scratch directory, its engine layouts kept | cache prune, cache cleanup, render sweep |
| extraction fixer | the `extraction-fixer` worker, one dispatch per defects file, that commits a defect-class fix on the fix branch or reports it unfixable | fixer (alone), repair worker, coder |
| fix branch | `extract-fixes/<date>`, the branch the extraction fixer commits on, merged through a pull request the orchestrator reviews | feature branch, work branch |
| regression check | `extract.py regress`, which rebuilds a sample of the reviewed works from their extraction records into the scratch directory and diffs each against its corpus file | regression test (for the check), regress run |
| citation link | the `[[<basename>|↗]]` Stage 3 writes after an entry or a footnote that names a held work with a corpus file | alias link, entry link |
| engine | marker, the conversion program Stage 2 runs in-process | converter, OCR (for the whole engine) |
| font repair | Stage 0's rewrite of a PDF's ToUnicode tables so the text layer emits the characters the page shows | glyph fix, font patch |
| identity table | `library/glyph-identities.json` in the vault, the characters a font's glyphs stand for, by font family | glyph map, mistake table |
| glyph-reader worker | the Stage 0 worker that names the character an unresolved glyph stands for from rendered regions | identifier, reader (alone) |
| pixel check | `fonts scan`'s pass that reads rendered lines and compares each glyph with the character the text layer emits | OCR check, visual check, glyph check |
| reading | the character the pixel check read at a glyph's position | OCR result, guess |
| plain glyph / symbol glyph | a glyph whose emitted character is a Latin letter, digit, or punctuation mark / any other glyph | text glyph, math glyph |
| text layer | the text a PDF embeds; the input to Stage 2 | extracted text (as a name for the corpus) |
| page checks | the per-page checks Stage 2 applies to the engine's output; the quality gate is one of them | sanity checks, quality check |
| quality gate | the language-independent measure of prose that the page checks include | quality check, sanity check |
| doubtful page | a page the page checks sent to a worker | bad page, failed page |
| omitted page | a page a worker judged unreadable: it contributes nothing to the body and carries no page marker | dropped page, skipped page |
| model servers | the engine's own long-lived processes, kept up across runs and stopped by `extract.py stop-servers` or by the idle reaper | surya servers, inference servers |
| idle reaper | the background process each `extract` starts, which stops the model servers after five minutes with no engine activity | watchdog, reaper (alone), timeout process |
| render | the rasterized image of one file page | screenshot, page image |
| readings file | the JSON list a page-reader dispatch returns | transcriptions file, worker output |
| opening | what `bibliographies.py opening` prints: a corpus file's headings and the text of its prefatory sections, or, when no prefatory section holds text, of its sections from the first that holds text, cut at 4,000 words | front matter, intro, prefatory unit |
| bibliography section | the section of a corpus file whose heading names the work's own reference list | references section, works cited (as a name) |
| embedding store | the vector half of the search stores | vector index, vector store, chroma (as a name) |
| full-text store | the BM25 half of the search stores | full-text search, keyword index |
| chunk context | the two lines a child chunk is embedded and indexed under: the work label, then its heading path | prefix, contextual prefix, situating context |
| work label | `<A and B>, <Year>, <Title>` from a corpus file's frontmatter, or its basename when one of the three is missing | document label, work header |
| hit | in Answer questions, one search result | match, candidate |
| reference list | the works a held work cites, extracted from its PDF | bibliography (of a work), works cited |
| entry list | a section Stage 2 rebuilds one entry per paragraph from the text layer's hanging indents: a bibliography or endnotes | reference list (for endnotes), note list |
| list of works | a bibliography's `## Primary works`, its `## Secondary literature`, or its `## Talk transcripts` | derived section, work list, works in library |
| read-only form / writing form | a script run without `--apply` / with `--apply` | preview, plan mode (for the read-only form) |
| annotation | one highlight plus its note, written into a library PDF | markup, marking |
| bracketed edition pagination | a bracket printed inline holding one or more references joined by `/`, each an edition siglum and a page, or a volume and a page; the `inline-marker` anchoring strategy | A/B markers, Akademie markers |
| annotation note | the text an annotation carries | note (alone), comment |
| gloss | the listed work's `description:`, copied whole after the work's wikilink on a bibliography's listing: what the work says it does, with its folio | annotation (for a bibliography), blurb, summary (for a gloss), entry note |
| introduction | the paragraph a bibliography opens with, before its first `##` section: one to three sentences on what the bibliography is about and what its listed works share | overview, preamble, synthesis (for the paragraph) |
| group note | the paragraph beneath a group's `###` heading, before its first listing: one or two sentences on what the group's works share | group gloss, group description, subheading note |
| annotated bibliography | a bibliography carrying glosses, an introduction, and group notes | reading guide (for a bibliography), survey |
| group | a `###` heading and what stands beneath it: inside a bibliography's list of works, its listings, `### Unsorted` holding the listings Stage 5 has sorted into no group; under `# Held` or `# Wanted` of a project reading list, its entries; under an atomic note's `# References`, its references | subsection (for a group), cluster (for a group), bucket |
| unsorted work | a listing in no group, or in `### Unsorted`, of a list of works that carries a group | ungrouped work, loose listing |
| reshaping | the tail step of a batch in which the bibliography shaper judges the citation graph's findings, the uncovered authors, the open nominations, the routing placements, and the fold candidates, and `reshape` creates and folds the bibliographies, moves the works its answers name, and removes every stray placement | restructuring, reorganization, tree update |
| part budget | the size one part of the bibliography shaper's listing keeps within: 240,000 bytes of the part's JSON on one line | size limit, cap, quota |
| bibliography shaper | the `bibliography-shaper` worker, one dispatch per part of the reshaping's listing, that writes the creations, the moves, the added placements, the links, the unlinks, and the folds to an answers file | shaper (alone), curator, organizer |
| narrower debate | a stretch of one bibliography's subject: the responses to it, its history, an approach to it, an aspect of it, a thesis about it, or the subject in one field; a `###` group on the subject's bibliography, never a bibliography of its own | sub-debate, subtopic, facet |
| fold | one bibliography the reshaping merges into the bibliography whose subject holds its own, because it gathers fewer than five works, or its subject is a narrower debate of the target's or a stretch of the target author's own writings: its works moved under a group, its maps relinked, its file deleted | merge (for a fold), collapse, absorption |
| fold candidate | a pair of bibliographies `shape-listing` names because the narrower one's name holds every word of the broader one's, or the last word of the bibliography that lists it, or because the narrower one gathers fewer than five works on it and beneath it and the broader one lists it | duplicate (for a candidate), merge candidate |
| author-only work | a work roled `primary` one of whose creators carries an author bibliography; it sits on its creators' author bibliographies and on no other bibliography | catalogue work, primary-only work |
| stray placement | an author-only work's placement on a bibliography other than its creators' author bibliographies, which the reshaping removes | misplaced primary, own-work placement |
| nomination | the bibliography a work classifier names for a work whose subject no bibliography names, recorded for the reshaping: its name, its kind, and its parent, a bibliography, one the tree lacks, or none for a new root; open until a reshaping moves its work | proposal (for a nomination), suggestion, candidate bibliography |
| creation | one bibliography the reshaping makes: its name, kind, parent, author, and the works that gather on it | new bibliography (for the answer), addition |
| move | one work the reshaping takes from one bibliography to another: its `field:`, its listing, and its placement | transfer, relocation |
| added placement | one work the reshaping places on one more bibliography, taking it off none | addition, second move, extra placement |
| link / unlink | one bibliography the reshaping adds to / takes out of one more parent's `## Maps` | attach, detach, reparent |
| line of descent | a chain of bibliographies, each listing the next under `## Maps` | branch, path (for the chain), lineage |
| most specific bibliography | of the bibliographies on a line of descent whose subject holds a work's subject, the one farthest from the root; the work sits there and on no ancestor of it | deepest bibliography, shallowest bibliography, lowest map, leaf |
| routing bibliography | a bibliography whose `## Maps` lists a bibliography other than a scholar's author bibliography, one no period lists; its own list of works holds only the works on the whole of its subject and on its narrower debates | upper map, parent map, hub |
| routing placement | a work on a routing bibliography other than its author's own, which the reshaping moves unless the work treats the whole of the bibliography's subject or a narrower debate of it | parked work, stray work, misplacement |
| relation test | the judgment whether a work treats the whole of a bibliography's subject, a narrower debate of it, a part of it, or a relation between it and another subject | relevance test, fit check |
| comparison bibliography | a bibliography on the relation between two subjects, listed beneath the most specific bibliography of each | cross map, bridge map, pairing bibliography |
| partner | another held work that shares the subject a work's nomination or routing placement names; a bibliography is created once a work and its partners number five | pair (for the work), match, sibling |
| thinker | an author whose works the library holds as the texts a period or a discipline studies; a period's `## Maps` lists its thinkers | primary author, figure, philosopher (for the class) |
| scholar | an author whose works interpret a thinker or a subject; the scholar's author bibliography sits beneath each subject its works treat | commentator, secondary author, interpreter |
| bibliography introducer | the `bibliography-introducer` worker, one dispatch per bibliography, that writes the bibliography's introduction, its group notes, and the group of each unsorted work to an answers file | introduction writer, gloss writer, bibliography composer, introducer (alone) |
| tag | the subtopic token on an annotation | label, subject, category |
| whole work | the Annotate mode that reads every page of one PDF | sweep, full pass |
| cross-page span | one annotation whose sentence runs over a page break, written as two highlights, one per file page | split highlight, spanning highlight, pair (for the span) |
| joint highlight | one highlight over several word spans of one file page, the passages a reference of an atomic note joins | compound highlight, grouped highlight, multi-part highlight |
| first segment / second segment | the highlight of a cross-page span on `page` / on `end_page` | half (for a segment), part |
| body line | a line of a page that is not a running head, a folio line, a footnote, or a banner | text line (for a body line), content line, prose line |
| citing work | in a trace, the work whose comments locate passages in another; in Discover, a held work whose reference list carries an entry | source work, commenting work |
| opaque title | a main title made of nothing but the names of persons, so that the filename would say nothing of what the work treats | bare title, vague title, unclear title |
| amended name | the filename title `<main title> on <subject>` Stage 1 gives a work whose opaque title has no subtitle, its reason recorded in the corpus file's `amended_name:` field | renamed title, descriptive title, invented title |
| ZotMoov | the Zotero plugin that names and places a PDF from its record | Zotero (as the namer) |
| stall signature | ZotMoov leaving a filed PDF unplaced | stall, hang |
| defect class | the property of a PDF that produces a failure, stated without naming a work | corner case, edge case, bug (for the class) |
| special case | a rule, a branch, a constant, or a table entry that only one work, or only the works of one batch, can meet | one-off, workaround, hack, exception (for a special case) |
| golden | a pinned expectation file under `tests/fixtures/goldens/` | baseline, snapshot (alone) |
| test suite | every test module under `tests/`, as `-m unittest discover -s tests` runs it | full suite, full test suite, whole suite |
| affected test modules | the test modules the post-edit hook runs after an edit to a Python file: each test module whose imports, or whose strings naming a `.py` file, reach the edited file | the test modules an edit affects, selected modules, the selection |
| post-edit hook | the hook in `.claude/settings.json` that runs `harness_hooks.py checks-after-edit` after every edit | edit hook, after-edit check |
| pre-push hook | `.githooks/pre-push`, which runs the test suite, the linter, and the audit linter's `works` check before every push from a checkout whose `core.hooksPath` names `.githooks` | push hook, pre-push check |
| checkout | the files of the control plane in one directory: the main checkout, or a worktree | work tree, clone (for a checkout) |
| worktree | a checkout `git worktree add` made beside the main checkout, sharing its repository | git worktree, linked work tree |
| audit baseline | `.claude/skills/vault-audit/baseline.json`, one digest per control-plane file as of the last accepted audit | manifest, snapshot (for the baseline) |
| audit set | the files one audit reads whole: those changed since the last accepted audit, plus every control-plane file that names one | audit scope, changed set, delta |
| conflict copy | a sibling file a sync service leaves beside a note or a store when two machines change it at once | conflicted copy, duplicate (for the file) |
| notation span | notation written as LaTeX between `$` delimiters, `$…$` inline and `$$…$$` displayed, the engine's reading and the form every downstream rule keys on; the legacy `❲…❳` placeholder of older corpus files is also one | placeholder (for a new span), delimited span, math span, inline math (as a name), equation (for an inline span) |
| math font | a font the text layer sets notation in, judged by `math_fonts.py` | symbol font, formula font |
| notation page | a page setting at least 5 characters in a math font or from the arrow and mathematical operator blocks, read from pixels | math page, formula page, notation chapter (for the pages read from pixels) |
| predicted pixel pages | the pages Stage 2 is expected to read from pixels: every page of a scan whose layer sample has not read its layer, or of a work its state records read from pixels only, else its notation pages with the pages its state records under `--pixel-pages` | OCR pages, pixel estimate |
| engine time | a work's predicted pixel pages times 100, plus its other pages: the engine's work on it, in pages read from the text layer | duration, runtime, estimate (for the time) |
| engine cost | a work's engine time, then its page count, compared in that order; the engine takes the work of the lower cost first | weight, size (for the cost), price |
| notation guard | Stage 2's check of each formula the engine reads against the text layer's characters for the same stretch, which agrees, corrects, or flags it | formula check, math verifier, LaTeX check |
| notation log | the report's `notation_log`: every formula the notation guard corrected or flagged, by file page | formula log, math log |
| prose guard | Stage 2's check of a notation page's prose words against the text layer the page draws, which takes the text layer's spelling where the engine slipped | word check, spell check, OCR correction |
| numeral guard | Stage 2's check of a numeral the engine reads with letters among its digits against a text layer that lies invisibly under the page image, which takes that layer's digits | digit fix, number check, OCR correction |
| text-layer page | a page that is not a notation page, written from the text layer's characters | prose page, plain page, text-layer chapter |
| statement label | the bold run-in label a work sets on a numbered definition, theorem, lemma, or their kin, which Stage 2 opens as a heading | theorem head, run-in heading |
| scout | the `literature-scout` worker, one dispatch per query cluster | searcher, search agent, crawler |
| grader | the `reading-list-grader` worker, one dispatch per reading list | reviewer, checker, evaluator |
| project reading list | `research vault/bibliographies/4 reading lists/<Project> - Reading list.md`, the questions it was searched for under `# Questions`, the works that bear on one project's questions, each held or wanted and sorted into `###` groups named for the parts of the questions, a wanted entry a plain line with no box, and its discover tasks under `# Neighbouring subjects`; never a bibliography | bibliography (for the list), literature review (for the file), reading list (alone, for a project's) |
| check-off | `ingest.py drive-readings`, once per batch after the reshaping: each wanted entry of a project reading list that names a placed work moved under `# Held` as the work's wikilink | tick-off, refresh (for the batch's step), reading-list sync |
| placed work | a held work whose `field:` names a bibliography | classified work, filed work (for a placed one), sorted work |
| reading list | the document Discover delivers | recommendations, bibliography (for the document), reading guide |
| neighbouring subject | in Discover and in a project reading list, a subject the question's subject draws on, applies, or runs parallel to, or one of two subjects the question relates, taken without the other; a work on it that holds no passage discussing the question does not bear on the question, and the subject is a discover task | related topic, adjacent topic, background (for the subject), vicinity |
| left-out work | in Discover, a search hit, a shortlist entry, or a candidate that the `discover` skill's "Scope" keeps off the reading list | excluded work, rejected candidate, off-topic work |
| discover task | `- [ ] #discover · Discover “<Subject>”: <how the subject bears on the question>`, one neighbouring subject at least two left-out works share, under a reading list's "Neighbouring subjects" or a project reading list's `# Neighbouring subjects`, which the user chooses by checking it or naming it | subtopic task, follow-up search, related reading list |
| seed work | a held work the vault search, or the corpus read, names as bearing on the question | anchor, source work (in Discover) |
| outer ring | in Discover, the works `list_works` returns for the bibliographies a seed work's `field:` names | neighbours, related works |
| citing set | in Discover, the seed works plus the outer ring, whose reference lists `unheld` reads | cluster (for held works), seed cluster |
| shortlist | the entries `unheld --min-citing <N>` prints over the citing set | top entries, frequent citations |
| known item | a shortlist entry the orchestrator chooses because the work it names bears on the question | known work, lookup target |
| known-item query | one query naming one known item by its first author's surname, then its main title in quotation marks | title query, lookup query |
| term list | the concepts, technical terms, position labels, and names Discover harvests from the seed works and the shortlist | keywords, vocabulary (alone), search terms |
| query cluster | the queries assigned to one scout, grouped by source | batch (for queries), query set |
| candidate | a work a scout saw a page for | hit (in Discover), result, finding |
| sighting | the page a candidate was seen at, a record page or a search listing | evidence, provenance |
| obtain link | the one link a reading-list entry carries to where the work is obtained | download link, access link, source link |
| citation parser | the token classifier `references.py` loads to split one reference entry into fields | NER model, tagger, the model (alone) |
| scored match | a held work an entry names by score rather than by the exact rule; automatic at or above the automatic threshold, in the middle band between the two thresholds | fuzzy match, candidate link |
| middle band | the scores between the confirmation threshold and the automatic threshold, reported in `to_confirm` | grey zone, uncertain matches |
| verdict | the citation judge's or the user's `confirm` or `reject` on one scored match: one citing work, one entry text, one matched work | decision, answer (for a verdict), ruling |
| citation judge | the `citation-judge` worker, one dispatch per listing of at most 120 middle-band matches, that writes a verdict on each to an answers file | matcher, link judge, citation reviewer |
| verdicts record | `library/citation-verdicts.json` in the vault, every verdict under its citing basename and entry text, which `cite.py settle --apply` writes | confirmations file, verdict store, sidecar |
| verdicts file | the JSON list of verdicts the orchestrator writes for `cite.py settle --verdicts` | answers file (for a verdicts file), input file |
| citation graph | every reference the corpus files make, held and unheld, each with the folio of the citing line, and the signals that relate two held works; `cites` and `cited_by` read its held edges, the citation links Stage 3 wrote | link graph, reference network |
| graph store | `citation-graph.sqlite` under `rag_dir`, which `graph.py sync` builds over the corpus files and the embedding store | graph database, graph cache |
| neighbours | the held works nearest one held work by the citation graph's combined signals, as `graph.py neighbours` lists them | related works (for the listing), similar works |
| cluster finding | one entry of `graph.py clusters`' `findings`: `new`, `split`, `misfit`, or `missing` | suggestion, recommendation (for a finding) |
| passage | in the citation graph, one stretch of a citing corpus file that speaks of a cited work, as `graph.py contexts` returns it | context (alone), snippet |
| heading tree | a corpus file's headings, each with its level, the folios it spans, and its first file page; what the `outline` tool returns | outline (for a corpus file), table of contents (for a corpus file), structure |
| passage grader | the `passage-grader` worker, one dispatch per work whose hits number more than six | grader (in Answer questions), relevance judge |
| work reader | the `work-reader` worker, one dispatch per work or per heading range | reader (in Answer questions), summarizer |
| page text | the matched span as the PDF's text layer has it, reported by `verify` | raw text, PDF wording, text-layer text |
| deep link | the `zotero://open-pdf/library/items/<KEY>?page=<file page>` link `verify` reports | Zotero link, PDF link (for the link at a page) |
| talk | one recorded talk, identified by its recording's URL | video, lecture (as a name), episode |
| recording | the video a talk's URL names | clip, stream, file (for the recording) |
| talk transcripts | `research vault/corpus/talk transcripts/`, the directory of transcripts, nested in the derived corpus and holding no corpus file | transcripts (for the directory), transcripts folder, talks (for the directory) |
| transcript | one note of the talk transcripts, `<basename>.md`: the frontmatter `file` writes and Stage 4 classifies, and the body the transcript reviewer wrote | transcription (for the note), talk note, transcript file |
| time marker | the Obsidian comment `%% hh:mm:ss %%` naming the second of the recording an utterance begins at | timestamp (for the marker), time code, time tag |
| utterance | one speaker's uninterrupted run of words, one paragraph of a transcript | turn (for the paragraph), segment (for the paragraph), speech |
| speaker line | `**<label>:** <text>`, the line an utterance's text opens with | speaker tag, name line |
| machine label | `SPEAKER_00`, `SPEAKER_01`, or `SPEAKER_UNKNOWN`, the label the diarization model assigned by voice | diarization label, speaker id, placeholder name |
| raw transcript | `raw.md` in a talk entry, one paragraph per utterance as the transcription engine heard it, each under a machine label | draft transcript, whisper output, auto transcript |
| talk entry | `~/.research-vault/cache/talks/<video id>/`, the scratch entry one talk passes through | talk folder, working dir, job |
| talk batch | the recording URLs the user gives in one message, or the playlist's new talks when the user asks for a check | queue, set |
| playlist | the YouTube playlist `machine.json` names under `talks_playlist`, kept by the user; each video on it is held, in progress, or new | watch list, feed, queue |
| talk listing | the JSON `transcribe.py review-listing` writes: the recording, the raw transcript in parts, and the paths to write | review listing (for a talk), listing (alone) |
| part | one slice of a listing that one dispatch judges: of a raw transcript in a talk listing, cut at a paragraph boundary at most 4,000 words in, reviewed to one file; or of the pages a scope listing or a review listing names, at most 12 pages, judged to one verdicts file; or of the entries the bibliography shaper's listing holds, within the part budget, judged to one answers file | chunk (for a part), section (for a part), piece |
| talk card | `card.json` in a talk entry: the `title`, `presenters`, `year`, `meeting`, and `dropped` the transcript reviewer records before the Zotero record exists | draft card (for a talk), metadata card, sidecar |
| transcript reviewer | the `transcript-reviewer` worker, one dispatch per talk, that writes the reviewed parts and the talk card | reviewer (alone), editor, cleaner |
| check | `transcribe.py review-check`, which passes or fails a review by its parts and its talk card | validation, verdict (for the command), gate |
| health watcher | the `machine-health` skill's `health.py sample`, which launchd runs once a minute on the primary | monitor, watchdog, daemon |
| health journals | `~/.research-vault/cache/health/`, the samples and the health alerts, one JSON-lines file per day | health log, metrics, telemetry |
| health alert | one detector's finding about the machine: critical memory pressure, or a serious or critical thermal state | warning, alarm, incident |
| project | one piece of the user's writing in progress, named by its project file's basename | paper (for a project), piece, essay (for a project) |
| project file | `research vault/writing/2 projects/<Project>.md`, the user's map of one project, an Excalidraw board: its parents and children in its frontmatter, its Markdown side, and its drawing | project note, hub, index (for a project file), canvas |
| board | the drawing of a project file: the research question's section card, a card for each atomic note and each source of the project, an arrow for each relation between two atomic notes, and the project card in its corner | map (alone), diagram, canvas |
| card | one box of a board, holding a title and words; an atomic note's card and a source's card link what they stand for | node, box, tile |
| section card | a card that shows what stands under `# Research question` or `# Project` of the Markdown side as Markdown the user reads and edits on the board | back-of-the-note card, embed (for a section card), Markdown card, panel |
| project card | the section card of `# Project`: the abstract, the link to the project reading list, the drafts, the open questions, and the change log, in the board's corner | legend, sidebar, info card, dashboard (for the card) |
| change log | the lines under `## Change log` of a project file: one dated line per atomic note added to or removed from the project, and per draft listed | history, journal, activity log, changelog |
| Markdown side | the headings of a project file above its drawing, which `sync` writes anew from the body of each: `# Research question`, `# Project` with its `##` headings, and `# Feedback` | back of the note, dashboard, text side |
| board state | the comment `%% board-state … %%` opening a project file's Markdown side, naming the notes, the relations, and the section cards the last `sync` left on the board | sync record, snapshot (for the state) |
| atomic note | `research vault/writing/1 notes/<Title>.md`, one to three claims of the user's under one idea's title, with their explications, the references behind them, and the tasks they leave | idea note, idea (for the note), permanent note, zettel, card (for an atomic note) |
| reading note | an atomic note whose claims report what one held work argues, as the text presents it | literature note, source note, reading card |
| relation | the words `<relation kind> [[<Title>]]` in an explication or in a reference's comment line of an atomic note, naming another atomic note and how the note relates to it | link (for a relation), connection, association |
| explication | a tab-indented `- <explication>` line beneath a claim of an atomic note: a precision, a clarification, or a relation of the claim | elaboration, sub-claim, gloss (for an explication) |
| reference | one verified quotation under an atomic note's `# References`: its quotation line, its source line, and its optional comment line | source line, citation (for a reference), evidence |
| quotation relation | one of `states`, `supports`, `explicates`, `discusses`, the bold word a reference's quotation line opens with | reference type, evidence kind |
| accepted mark | ` #accepted` closing a line of an atomic note the user has reviewed and keeps, a reference on its quotation line, written in place of the review mark by the user, or by `accept` on a note whose accept task the user checked; a line that carries it is never changed or deleted, and `highlight` writes a highlight for no reference without it | approved tag, noted, done mark, checked |
| accept task | `- [ ] #accept · Accept every line of this note marked for review`, the first line under every atomic note's `# Tasks`, which the user checks to accept every line of the note marked for review; it is no task | approve box, sign-off task, accept-all |
| review mark | ` #review` closing a line the orchestrator, a note researcher, or the note reviewer wrote or changed in an atomic note, one to a reference, on its quotation line, or the orchestrator proposed under a project file's `# Research question`, `## Abstract`, or `## Open questions`, which the user alone removes, by hand or, in an atomic note, by checking its accept task | review tag, proposal mark, flag |
| note researcher | the `note-researcher` worker, one dispatch per atomic note of a batch or per chosen task, that researches the note and writes into it through `notes.py` | note taker (for the worker), researcher (alone) |
| relation kind | one of `extends`, `supports`, `contradicts`, `example of`, `presupposes`, `descends from`, the words a relation opens with | link type, relation type, edge label |
| field | the `field:` of an atomic note or a project file: the bibliographies its subject belongs to, written in its frontmatter alone, which no bibliography lists back | placement (for a note's field), classification (for a note's field), tag (for a field), listing (for a field) |
| task | a `- [ ] #<tag> · <Verb> …` line naming a step the orchestrator or a worker carries out, its tag naming the step's kind and the verb the step, and never a step only the user can take: under an atomic note's `# Tasks`, `#<thread> · Take notes on “<Title>” …`, naming one further atomic note that a thread of the note leads to, or, as an `enrich` task, `#enrich · Read <the source> for this note …`; under a reading list's "Neighbouring subjects" or a project reading list's `# Neighbouring subjects`, a discover task | to-do item, action item, reminder, branch (for a task), suggestion (for a task) |
| thread | what a task is to the note it stands in, written as the task's tag: one of `focus`, `enrich`, `conceptual`, `genealogical`, `contrary`; an `enrich` task names further reading for the same note, the others a further atomic note | branch kind, task type, lead |
| chosen task | a task of an atomic note the user has checked, `- [x]`, or names in chat: the task to resolve | selected task, ticked task, done task |
| reviewed note | the atomic note the note reviewer revises: the note whose chosen tasks are resolved, or a note the user asks to be reviewed | original note, parent note, source note (for a reviewed note) |
| note reviewer | the `note-reviewer` worker, one dispatch per reviewed note, that relates the note to each further note, rewords its claims to state what its references support, and fits its tasks to them | reviewer (alone), reviser, note editor |
| child project | a project another project's `children:` lists, its own `parents:` listing that project | subproject, part, chapter (for a child project) |
| draft | a file of `research vault/writing/3 drafts/` holding one version of a project's text, a whole draft, or of one section, a section draft | manuscript, working copy |
| version | the two-digit number that closes a draft's name, the latest the highest | revision (for the number), iteration |
| Word file | a `.docx` in the inbox, a draft the user wrote outside the vault, which `drafts.py import` converts into a draft | Word document, docx (alone), original (for the file) |
| export style | the formatting `drafts.py export` gives a `.docx` or a PDF, `submission` or `reading` | template, preset, theme |
| citation style | a `.csl` file of `~/Zotero/styles/`, named without its suffix, that sets how an export writes its citations and its bibliography | CSL (alone), reference style, bibliography format |
| finding | in Edit drafts, one thing a check found in a draft: its line, the words it concerns, what is wrong, and the fix proposed | issue, error (for a finding), suggestion (for a finding) |
| editor's comment | the Obsidian comment `%% editor: <finding> %%` written on the line after the paragraph a finding concerns | inline suggestion, margin note, annotation (for a comment) |
| level | in Edit drafts, one of `structure`, `line`, `copy`, `proof`: the kind of editing a check does | pass (for a level), stage (for a level), tier |
| coverage | for each claim a draft makes, the atomic note that holds the claim, or none | mapping, traceability |
| published piece | a finished whole draft copied into `research vault/writing/4 published/` under its own title | final version, finished draft |
| thermal state | the reading macOS reports for the machine's heat: `nominal`, `fair`, `serious`, or `critical`; a batch update reports the worst over the interval | temperature (for the state), heat level |

The code and configuration identifiers `vault-rag`, `rag.py`, `RAG_DIR`,
`rag_dir`, and `itemType` stay as written.

## Defect class

**In the vault, `clean-prose` §12's input is a PDF and the work it holds, and
its run is a batch.** The contract's §5 defines the defect class and the
special case, and prohibits the special case.
