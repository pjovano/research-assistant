# Retrieval (reference: how a research skill searches the library, reads it, and quotes it)

A research skill loads this file before it searches, reads, or quotes the library.

## Rigor

**These rules bind every research skill, and each research worker's
instructions restate the ones that bind the worker.**

| Rule | Binds |
| --- | --- |
| read before citing | NEVER cite a work, a passage, or a folio that was not read in the session, in the corpus file or on the page |
| the closest passage | A passage supports a claim only if the passage states the claim. NEVER cite a passage that only shares the claim's subject |
| attribution | Attribute to an author only what the author's text states. If a claim is an inference from the text, write the claim as an inference and cite the passage it is drawn from |
| primary text and secondary literature | Name which cited works are primary texts and which are secondary literature. Report a reading of a primary text from the secondary literature that makes the reading, per "Choose the works" |
| edition and translation | Cite the edition the library holds. If a citing work quotes a passage in another translation than the held one, say so beside the quotation |
| disagreement | Report a disagreement between sources as a disagreement, and name who holds which position. NEVER merge two positions into one |
| absence | If the library holds no passage for a claim, say so. NEVER fill the gap from memory as though from the library |
| uncertainty | If a folio, a reading, or an attribution is uncertain, state the uncertainty beside it |

## Two kinds of statement

**The corpus files are what the answer is built from.** A claim about what
a work argues, defines, proves, or holds, and every summary, comparison, and
survey, is written from the corpus files: their bodies, their frontmatter,
and the bibliographies that place them. A corpus file is the work's text as
the engine read it, with a page marker where each page begins, so a claim
carries the folio the marker names.

**A direct quotation is verified in the PDF.** A quotation is a span of the
work's words delivered as the work's words, in quotation marks or set off
as a block. NEVER deliver a quotation from a corpus file: the corpus file
locates it, the PDF confirms it, and the words delivered are the page's own,
as `verify` reports them.

**A transcript is paraphrased, never quoted.** A transcript is a note of
`research vault/corpus/talk transcripts/`, the transcript reviewer's reading of a
recorded talk: its `source_type` is `transcript`, its first line is
`[Recording](<url>)`, the recording's URL, its frontmatter carries the
`meeting` the talk was given at, and a time marker `%% hh:mm:ss %%` opens
each utterance. A hit in a transcript carries
`time_first` and `time_last` in place of folios, and `outline` gives each
heading its `time_first`. NEVER deliver a transcript's words as a speaker's
words, in quotation marks or as a block: report what the speaker argues in
the orchestrator's words, cited `<Presenter> <Year>, <hh:mm:ss>` by the
hit's `time_first`, with the recording's URL, read from the transcript's
first line, at the first citation. Where
a transcript and a corpus file bear on one question, the answer names which
is which.

## The surfaces

| Surface | Job |
| --- | --- |
| the search stores (`search_hybrid`, `search.py query`) | which works and which passages bear on the question; a hit carries the passage, its heading path, its folio range, or its time range in a transcript, its `parent_id`, and `matched_start` and `matched_end`, the offsets within the passage of the child chunk that matched |
| a work's heading tree (`outline`, `search.py outline`) | every heading of one corpus file or transcript with its level, the folios it spans, its first file page, its `time_first` in a transcript, and its word count; the work's word count |
| a corpus file's or a transcript's frontmatter (`get_frontmatter`) | the work's identity, `source_type`, `source_role`, `field:`, and `uncitable`; a transcript's `meeting` |
| a work's extraction record (`extract.py record`) | `mode`, present as `forced-ocr` only on a work read from pixels |
| the bibliographies (`list_works` with a `field`) | the other works on the same bibliography |
| the citation graph (`cites`, `cited_by`, `neighbours`, `contexts`) | which held works a corpus file links to in its bibliography entries and footnotes, and which corpus files link to a held work, each edge with the folio of the linking line; the works nearest a held work by citation and by embedding, with the signals behind each; and the passages where one held work speaks of another, each with its folio |
| a corpus file's body | the text the answer is built from, read in the sections the hits name |
| a term's pages in the PDF (`verify.py locate "<basename>" "<term>"`) | the file pages whose text layer carries the term, each with its folio |
| the PDF in the library | the page a quotation is verified on |

## The workers

| Worker | Worker instructions | Dispatched when | Returns |
| --- | --- | --- | --- |
| passage grader | `.claude/agents/passage-grader.md` | one work's surviving hits number more than six; one dispatch per such work | per hit, a grade and the sentences that bear on the question, each with its folio |
| work reader | `.claude/agents/work-reader.md` | the question is about one held work's argument as a whole; one dispatch per work, or per heading range of a work over 150,000 words | the work's claims as it bears on the question, in text order, each with its folio |

Both run on the session's model: dispatch with `Agent`, `subagent_type`
naming the worker, and pass no `model`. The prompt carries the corpus file's path in full:
`<CORPUS_DIR>/<basename>.md`, where `CORPUS_DIR` is the path
`~/.research-vault/venv/bin/python lib/vault.py` prints under that name. A
worker that returns no JSON object, or `{"error": …}`, is a failed dispatch: dispatch it once
more; if it fails again, read the sections yourself per "Read" and say in
the answer that the worker failed.

**NEVER dispatch a worker on a transcript:** both workers read page
markers, and a transcript carries time markers. Read a transcript's sections
yourself, as "Read" reads six hits or fewer, from
`<TRANSCRIPTS_DIR>/<basename>.md`, where `TRANSCRIPTS_DIR` is the path
`lib/vault.py` prints under that name.

## Search

`search_hybrid` takes one query or a list of them, and a list
is fused and reranked in one call: PREFER one call carrying every query
OVER one call per query, which costs a rerank and a payload each. Search
for each of:
1. the question as phrased;
2. one rephrasing of it;
3. the bare key terms;
4. each key term in German and in French, and in Latin or Greek where the
   term has a standard form in that language: *being* is also *Sein*,
   *être*, *esse*, and *τὸ ὄν*; *essence* is also *Wesen*, *essence*,
   *essentia*, and *οὐσία*.

The embedder is not trained on Latin or Greek, so a passage in those
languages is reached through the full-text store only when the query
carries the word the page carries. One call over several queries returns
each parent once; across separate calls, two hits with the same
`basename` and `parent_id` are one hit.

| Search outcome | Do |
| --- | --- |
| the MCP server is unavailable | run `~/.research-vault/venv/bin/python .claude/skills/search/scripts/search.py query "<text>"` for each query; if that also fails, stop and tell the user the search stores are unavailable |
| a result carries `{"warning": "… keyword-only …"}` | say in the answer that the results are full-text only |
| a result carries `{"warning": "reranker unavailable: …"}` | say in the answer that the results are the fused ordering |
| a result carries `{"reranker": "used: …"}` | nothing: the reranker ordered the hits |
| a result carries `{"warning": "stale: …"}` | say in the answer that the named works changed since they were indexed, and tell the user to run Stage 6 |

## Choose the works

| The question is about | Do |
| --- | --- |
| one held work's argument as a whole: its thesis, its structure, how it develops | dispatch the work reader on that work and build the answer from what it returns; if `outline` reports more than 150,000 words, split the work by top-level heading into ranges of at most 150,000 words and dispatch one work reader per range, in one message. Search still runs, to find the secondary literature the table below requires for an interpretive question |
| who responds to, engages with, or builds on a held work | walk the citation graph before searching: run `cited_by` on the work; every corpus file it returns cites the work, and the folio names the citing entry. Run `cites` on a corpus file to find the held works it builds on, and `contexts` on a citing and a cited work to find the passages where the one speaks of the other, each with its folio. `cites` and `cited_by` hold only the links Stage 3 wrote, so a work cited in prose without a bibliography entry or footnote is absent from them; `contexts` finds a prose citation and a title mention besides: if the graph returns nothing, search per "Search" and say in the answer that the graph was empty |
| anything else | choose the works by the kind of question, from the table below |

Read the frontmatter of each promising hit; `source_type` and
`source_role` say what each work is. Use `list_works` with the hit's
`field:` to find the works the hits missed.

| Question | Built from | The primary work's corpus file is |
| --- | --- | --- |
| a definition, a theorem, a technical concept | reference works first, then monographs | the source of a quoted definition or theorem |
| what a philosopher holds, argues, or means, or how a work has been read | the secondary literature on the work, always ahead of the orchestrator's own reading of the primary text | a locator: it names where the philosopher treats the matter, and those passages are cited as the ones the secondary literature reads |

Secondary literature is every held work about the primary work, whatever
its `source_role`; no role ranks above another. NEVER answer an
interpretive question from the orchestrator's own reading of the primary
text where the vault holds secondary literature on it: contract §1
forbids interpreting a source, and a reading reported from the secondary
literature is a report, the orchestrator's is not. If the vault holds no
secondary literature on the work, say so, and draw the
interpretation from the literature outside the vault, cited.

## Read

For each chosen work, run `outline` and name the section each
hit falls in: the entry whose `heading_path` the hit carries. If `outline`
returns `{"error": …}`, read only each hit's passage for that work and say
in the answer that its heading tree was unavailable. Then:

| The work's surviving hits | Do |
| --- | --- |
| more than six, in a corpus file | dispatch one passage grader with the question and the work's hits; read only the sections it grades `relevant` or `partly`, and take the sentences it returns with their folios |
| six or fewer, or in a transcript | read the section each hit falls in, from its heading to the next; if the section runs past 4,000 words, read the 4,000 words around the hit |

Either way the folio a claim rests on is the folio of the nearest page
marker before it.

## Verify every direct quotation

For each quotation the answer will
carry:
1. find it in the corpus file and read the folio from the page marker;
2. open the PDF at that folio and read the page;
3. run

       ~/.research-vault/venv/bin/python .claude/skills/answer-questions/scripts/verify.py verify "<basename>" "<the exact quotation>"

   with the quotation as the corpus file writes it, notation as its
   notation spans.

| Verdict | Exit | Do |
| --- | --- | --- |
| `VERIFIED` | 0 | deliver the `page text` line, citing the folio reported, with the `link` reported beside it |
| `VERIFIED (prose only)` | 0 | the quotation carries notation: the prose is verified by text; read each notation span `verify` lists on the page and write the notation as the page sets it, then deliver the quotation as above. NEVER deliver a notation span's LaTeX as the work's notation without reading it on the page: the engine can misread a symbol |
| `NEAR MATCH ONLY` | 1 | correct the wording against the `page text` shown and verify again, or quote a shorter exact span; NEVER deliver it as-is |
| `AMBIGUOUS` | 1 | the quotation appears word for word on more than one page, each listed with its file page and folio; quote a longer span that appears on one page only, then verify again |
| `NOT FOUND` | 1 | do not deliver it; re-read the page. If the corpus file carries `uncitable:`, see below |
| a usage error | 2 | correct the command and run it again |
| any other verdict, or an error | 4 | stop and tell the user the message |

**The words delivered are the page's, not the corpus file's.** `verify`
reports the matched span as the PDF's text layer has it under `page
text`, with line-break hyphens joined and whitespace collapsed; deliver
that wording. `verify` reports the file page beside the folio and, when
the corpus file's body begins with its PDF link line, a `link` of the
form `zotero://open-pdf/library/items/<KEY>?page=<file page>`; if the
line is absent, `verify` says so and the quotation carries no link. A
quotation that runs across a page break is verified at its first page:
`verify` reports that page's file page and folio and a `spans pages` line
naming both file pages.

**The folio `verify` prints names its source.** `(corpus)` is the folio
the corpus file's page marker carries for that file page, and it is the
folio to cite; `(text layer)` is the folio read from the page itself,
printed where the corpus file marks no folio for that page. If the two
sources would disagree, `verify` reports the corpus file's, so a citation
matches the page marker a claim rests on.

If `extract.py record "<basename>"` reports `mode: forced-ocr`, or `verify.py
quality "<basename>"` exits 3 (a poor text layer), the text layer cannot
confirm a quotation: read the page visually, deliver the quotation as
read from the page, and say so beside it.

## `uncitable:`

**A corpus file carrying `uncitable:` in its frontmatter describes a
published version while the PDF held is a different setting**, so the
published folios are not in the file and `verify` fails however accurate the
quotation. If a quotation fails, check for the field before concluding it is
bad:

    Grep "^uncitable:" in "<CORPUS_DIR>/<basename>.md"

`CORPUS_DIR` is the path `~/.research-vault/venv/bin/python lib/vault.py`
prints under that name. If the corpus file carries the field: NEVER loop on re-reading. Read the PDF
for the quotation; cite chapter and section, never a page counted in the
file; and state in the answer that the page could not be checked against the
copy held. NEVER present a page-level citation from such a work as verified.
