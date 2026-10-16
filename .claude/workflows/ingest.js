export const meta = {
  name: 'ingest',
  description: 'The ingest batch: each PDF through Stages 0 to 4, then the bibliographies check beside the citation sweep, the reshaping, the check-off of the project reading lists, Stage 5 on the bibliographies touched, and Stage 6, once',
  whenToUse: 'a batch, args {from: "clean"}; a backfill, args {from: "extract", start, end} after extract.py drive-queue; works names the keys of the works to carry instead of the listing, from ingest.py list-works; gloss: "all" glosses every bibliography in the tail; gloss: "none" skips Stage 5; index: false skips Stage 6; cleanup: true sends each trial through the text-only cleanup before Stage 2 accepts it',
  phases: [
    { title: 'Preflight', detail: 'the machine checks, once' },
    { title: 'Clean', detail: 'Stage 0: pdf-cleaner, the font repair, pdf-bookmarker' },
    { title: 'File', detail: 'Stage 1: pdf-filer; the Zotero connector one PDF at a time' },
    { title: 'Extract', detail: 'Stage 2: the engine one PDF at a time; the workers overlap' },
    { title: 'Cite', detail: "Stage 3: the work's citation links and the links naming it; the corpus files one work at a time" },
    { title: 'Classify', detail: 'Stage 4: work-classifier, reading the citation graph; the bibliographies one work at a time' },
    { title: 'Shape', detail: 'the reshaping: one bibliography-shaper per part of the listing of the citation graph\'s findings, the uncovered authors, and the open nominations' },
    { title: 'Gloss', detail: "Stage 5: each work's description copied onto its listings, then bibliography-introducer on each bibliography the batch touched" },
    { title: 'Tail', detail: 'the bibliographies check beside the citation sweep, citation-judge on its middle band, then the check-off of the project reading lists, Stage 5, and Stage 6, once' },
  ],
}

const PYTHON = '~/.research-vault/venv/bin/python'
const REPOSITORY = '~/Developer/research-tools'
const SCRIPTS = {
  clean: skillScript('clean-pdfs/scripts/clean.py'),
  file: skillScript('file-pdfs/scripts/file.py'),
  extract: skillScript('extract-corpus/scripts/extract.py'),
  bibliographies: skillScript('classify-and-place/scripts/bibliographies.py'),
  search: skillScript('search/scripts/search.py'),
  ingest: skillScript('ingest/scripts/ingest.py'),
}

function skillScript(path) {
  return `${PYTHON} ${REPOSITORY}/.claude/skills/${path}`
}
const STAGES = ['clean', 'file', 'extract', 'cite', 'classify']
const PHASE_OF = { preflight: 'Preflight', clean: 'Clean', file: 'File', extract: 'Extract', cite: 'Cite', classify: 'Classify', shape: 'Shape', gloss: 'Gloss', tail: 'Tail' }
const ENGINE_STEPS = new Set(['drive-prep', 'drive-trial', 'drive-retrial'])
const CONVERTING_STEPS = new Set(['drive-fonts', 'drive-prep'])
const CONVERTED_TIER = 0
const UNCONVERTED_TIER = 1
const RELAY_ATTEMPTS = 2
const RELAYED_AGAIN_STAGES = new Set(['preflight', ...STAGES])
const UNWRITTEN = 'unwritten'
const WORKER_ATTEMPTS = 2
const FONTS_CHECKED_FLAG = '--fonts-checked'
const PIXELS_ONLY_FLAG = '--pixels-only'
const PIXEL_PAGES_FLAG = '--pixel-pages'
const FONTS_CHECKED_STATE = 'fonts-checked'
const AWAIT_FONTS_FLAG = '--await-fonts'
const ONE_CHAPTER_FLAG = '--one-chapter'
const CLEANUP_FLAG = '--cleanup'
const UNTRUSTED_LAYER_LINE = 'The text layer of this file cannot be trusted: take every title from the render, never from the text layer.'
const MAX_LOOPS = 8
const MAX_CLEANER_DISPATCHES = 2
const MAX_CARD_ROUNDS = 4
const CLEANING_AT_ONCE = 4
const WORKS_PER_RUN = { clean: 45, extract: 55 }
const SONNET = 'sonnet'
const SCOPE_NOTE_OPENING = {
  rescope: 'Your previous verdicts need a new scope; judge the listing with this note in view:',
}
const SCOPE_DISPATCH_STATES = new Set(['ready', 'rescope', 'rejudge'])
const TAIL_KEY = 'tail'
const PREFETCH_KEY = 'prefetch'
const WORK_FILE = 'work.json'
const WHOLE_BATCH_STAGES = new Set(['preflight', 'tail'])
const STOPPING_STATES = new Set(['unreadable', 'aside'])
const REPLY_OPENING_CHARS = 300
const KIND_PHRASE = { article: 'an article', book: 'a book', volume: 'an edited volume' }
const NUMBER_SLOT = '{n}'
const COUNT_FIELD = 'count'

const CLEANER_REPORT = {
  type: 'object',
  properties: {
    kind: { type: 'string', enum: ['article', 'book', 'volume', 'none'] },
    cover: { type: 'string', enum: ['final', 'none-found', 'not-searched'] },
    partial: { type: 'boolean' },
    stopped_on: { type: 'array', items: { type: 'string' } },
  },
  required: ['kind', 'cover', 'partial', 'stopped_on'],
}
const BOOKMARKER_REPORT = {
  type: 'object',
  properties: {
    outcome: { type: 'string', enum: ['kept', 'pruned', 'built', 'no-divisions', 'failed'] },
    toc_found: { type: 'boolean' },
    checklist: { type: 'integer' },
    confirmed: { type: 'integer' },
    unfound: { type: 'array', items: { type: 'string' } },
    stopped_on: { type: 'array', items: { type: 'string' } },
  },
  required: ['outcome', 'toc_found', 'checklist', 'confirmed', 'unfound', 'stopped_on'],
}
const FILER_REPORT = {
  type: 'object',
  properties: {
    citekey: { type: 'string' },
    title_opaque: { type: 'boolean' },
    unestablished: { type: 'array', items: { type: 'string', enum: ['title', 'creators', 'year'] } },
    uncertain: { type: 'array', items: { type: 'string' } },
  },
  required: ['citekey', 'title_opaque', 'unestablished', 'uncertain'],
}
const OPAQUE_VERDICT = {
  type: 'object',
  properties: { opaque: { type: 'boolean' } },
  required: ['opaque'],
}

function limit(size) {
  let active = 0
  const waiting = []
  return async (task, rank = 0) => {
    if (active < size) active++
    else await new Promise(resume => enqueueByRank(waiting, { rank, resume }))
    try {
      return await task()
    } finally {
      const next = waiting.shift()
      if (next) next.resume()
      else active--
    }
  }
}

function enqueueByRank(waiting, entry) {
  const firstRankedLater = waiting.findIndex(waiter => rankOrder(waiter.rank, entry.rank) > 0)
  waiting.splice(firstRankedLater < 0 ? waiting.length : firstRankedLater, 0, entry)
}

function rankOrder(first, second) {
  const firsts = [first].flat()
  const seconds = [second].flat()
  const differing = firsts.findIndex((part, index) => part !== seconds[index])
  if (differing < 0) return 0
  return firsts[differing] < seconds[differing] ? -1 : 1
}

const workCosts = new Map()
const UNKNOWN_COST = [Infinity, Infinity]

function engineRank(step, key, convertedPages = 0) {
  if (CONVERTING_STEPS.has(step)) return [UNCONVERTED_TIER, ...(workCosts.get(String(key)) ?? UNKNOWN_COST), Number(key)]
  return [CONVERTED_TIER, convertedPages, Number(key)]
}

const onEngine = limit(1)
const onZotero = limit(1)
const onTable = limit(1)
const onBibliographies = limit(1)
const onCitations = limit(1)
const onCleaning = limit(CLEANING_AT_ONCE)

const ARGS = args || {}
const FROM = ARGS.from || 'clean'

let halt = null

class Paused extends Error {
  constructor(stage) {
    super(`paused at ${stage}`)
    this.stage = stage
  }
}

function proceed(stage) {
  if (halt) throw new Paused(stage)
}

function quoted(text) {
  return `'${String(text).replace(/'/g, `'\\''`)}'`
}

const CODE_FENCE_LINE = /^`{3,}\w*$/
const SURROUNDING_BACKTICKS = /^`+|`+$/g

function jsonLineOf(reply) {
  const line = parsedReplyOf(reply)
  if (!isJsonObject(line)) throw new Error('the reply ends in JSON that is not an object')
  return line
}

function parsedReplyOf(reply) {
  const lines = String(reply).trim().split('\n').map(line => line.trim()).filter(line => !CODE_FENCE_LINE.test(line))
  try {
    return JSON.parse(lines[lines.length - 1].replace(SURROUNDING_BACKTICKS, ''))
  } catch {
    return JSON.parse(lines.join('').replace(SURROUNDING_BACKTICKS, ''))
  }
}

function isJsonObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

async function relay(command, label, phase, attempts) {
  let reply = ''
  for (let attempt = 1; attempt <= attempts; attempt++) {
    const attemptLabel = attempt === 1 ? label : `${label}, relayed again`
    reply = await agent(command, { label: attemptLabel, phase, model: 'haiku', effort: 'low', agentType: 'relay' })
    try {
      return jsonLineOf(reply)
    } catch {
      continue
    }
  }
  return unreadable(label, command, reply)
}

function unreadable(label, command, reply) {
  const opening = String(reply).slice(0, REPLY_OPENING_CHARS)
  return { state: 'unreadable', question: `${label} returned no JSON line; the command relayed: ${command}; the reply opens: ${opening}` }
}

async function drive({ stage, script, step, target, extra, onLock }) {
  proceed(stage)
  const command = [SCRIPTS[script], step, target === undefined ? '' : quoted(target), extra || ''].filter(Boolean).join(' ')
  const run = () => {
    proceed(stage)
    const attempts = RELAYED_AGAIN_STAGES.has(stage) ? RELAY_ATTEMPTS : 1
    return relay(command, target === undefined ? step : `${step} ${target}`, PHASE_OF[stage], attempts)
  }
  const line = settledReply(stage, onLock ? await onLock(run) : await run())
  if (line.state === 'halt' && !halt) halt = line.question
  return line
}

function settledReply(stage, line) {
  const wholeBatch = WHOLE_BATCH_STAGES.has(stage)
  if (wholeBatch && STOPPING_STATES.has(line.state)) return { ...line, state: 'halt' }
  if (line.state === 'unreadable') return { ...line, state: 'aside', unread: true }
  return line
}

async function writtenOnRedispatch(step, dispatch) {
  const line = await step()
  if (line.state !== UNWRITTEN) return line
  await dispatch()
  const again = await step()
  return again.state === UNWRITTEN ? { ...again, state: 'aside', question: `${again.question}, dispatched twice` } : again
}

async function detached(stage, key, command) {
  let line = await drive({ stage, script: 'ingest', step: 'drive-detach', target: key, extra: `-- ${command}` })
  while (line.state === 'running') line = await drive({ stage, script: 'ingest', step: 'drive-wait', target: key })
  return line
}

function worker(stage, prompt, options) {
  proceed(stage)
  return agent(prompt, { phase: PHASE_OF[stage], ...options })
}

async function settledWorker(stage, prompt, options) {
  try {
    return await worker(stage, prompt, options)
  } catch (error) {
    if (error instanceof Paused) throw error
    return null
  }
}

async function reportOf(stage, prompt, options) {
  for (let attempt = 1; attempt <= WORKER_ATTEMPTS; attempt++) {
    const label = attempt === 1 ? options.label : `${options.label}, dispatched again`
    const report = await settledWorker(stage, prompt, { ...options, label })
    if (report) return report
  }
  return null
}

function aside(stage, question) {
  return { stage, state: 'aside', question }
}

function workFileOf(byKey, key) {
  return `${byKey}/${key}/${WORK_FILE}`
}

function inboxPdfLine(workFile) {
  return `Work file: ${workFile}; its pdf names the PDF, in the inbox.`
}

function libraryPdfLine(workFile) {
  return `Work file: ${workFile}; its pdf names the PDF, in the library.`
}

function cleaner(workFile, previous) {
  const lines = [inboxPdfLine(workFile)]
  if (previous && previous.cover === 'not-searched') lines.push('Your previous report did not search for a jacket: search for one, and report what you found.')
  return worker('clean', lines.join('\n'), { label: 'pdf-cleaner', agentType: 'pdf-cleaner', model: SONNET, schema: CLEANER_REPORT })
}

function needsAnotherCleaner(report) {
  return !report || report.partial || (report.cover === 'not-searched' && report.kind !== 'article')
}

async function cleanerReport(workFile) {
  let report = null
  for (let dispatch = 0; dispatch < MAX_CLEANER_DISPATCHES && needsAnotherCleaner(report); dispatch++) {
    report = await cleaner(workFile, report)
  }
  if (!report || report.partial) return aside('clean', 'pdf-cleaner stopped before its report twice')
  if (needsAnotherCleaner(report)) return aside('clean', 'pdf-cleaner did not search for a jacket twice')
  if (report.kind === 'none') return aside('clean', 'pdf-cleaner judged the file none of an article, a book, or an edited volume')
  if (report.stopped_on.length) return aside('clean', `pdf-cleaner stopped on: ${report.stopped_on.join(' | ')}`)
  return { state: 'cleaned', kind: report.kind }
}

async function repairFonts(key) {
  const scanned = await onEngine(() => detached('clean', key, `${SCRIPTS.clean} drive-fonts ${quoted(key)}`),
    engineRank('drive-fonts', key))
  if (scanned.state !== 'glyphs') return scanned
  const groups = numbered(scanned.dir, scanned.groups)
  await readGlyphs(groups)
  return writtenOnRedispatch(() => drive({ stage: 'clean', script: 'clean', step: 'drive-learn', target: key, onLock: onTable }),
    () => readGlyphs(groups))
}

async function readGlyphs(groups) {
  for (const group of groups) {
    await settledWorker('clean', `Identify listing: ${group.codes}\nWrite your answers to: ${group.answers}`,
      { label: 'glyph-reader', agentType: 'glyph-reader', model: SONNET })
  }
}

async function bookmark(pdfLine, kind, pixelsOnly) {
  const lines = [pdfLine, `Kind: ${KIND_PHRASE[kind]}.`, 'The cover work on this file is final.']
  if (pixelsOnly) lines.push(UNTRUSTED_LAYER_LINE)
  const prompt = lines.join('\n')
  const report = await reportOf('clean', prompt, { label: 'pdf-bookmarker', agentType: 'pdf-bookmarker', model: SONNET, schema: BOOKMARKER_REPORT })
  if (!report) return aside('clean', 'pdf-bookmarker stopped before its report twice')
  if (report.outcome === 'failed') return aside('clean', 'pdf-bookmarker could not write an outline')
  if (kind === 'volume' && report.outcome === 'no-divisions') return aside('clean', "a volume's outline is its contents, and none was written")
  if (report.stopped_on.length) return aside('clean', `pdf-bookmarker stopped on: ${report.stopped_on.join(' | ')}`)
  return { state: 'bookmarked', unfound: report.unfound, divided: report.outcome !== 'no-divisions' }
}

async function clean(key, workFile, notes) {
  const judged = await cleanerReport(workFile)
  if (judged.state !== 'cleaned') return judged
  const repaired = await repairFonts(key)
  if (repaired.state !== 'bookmark') return { stage: 'clean', ...repaired }
  notes.push(...(repaired.notes || []))
  const pixelsOnly = Boolean(repaired.force_ocr)
  const bookmarked = await bookmark(inboxPdfLine(workFile), judged.kind, pixelsOnly)
  if (bookmarked.state !== 'bookmarked') return bookmarked
  notes.push(...bookmarked.unfound.map(entry => `not found for the outline: ${entry}`))
  const routed = await drive({ stage: 'clean', script: 'clean', step: 'drive-route', target: key, extra: `--kind ${judged.kind}` })
  return { stage: 'clean', ...routed, pixels_only: pixelsOnly }
}

function filer(workFile, note) {
  const lines = [inboxPdfLine(workFile), 'Do not run file, retry, refile, or relink.']
  if (note) lines.push(note)
  return reportOf('file', lines.join('\n'), { label: 'pdf-filer', agentType: 'pdf-filer', schema: FILER_REPORT })
}

async function isOpaque(title) {
  proceed('file')
  const verdict = await agent(
    `Title: ${title}`,
    { label: 'opaque-title check', phase: PHASE_OF.file, agentType: 'title-checker', model: 'haiku', effort: 'low', schema: OPAQUE_VERDICT })
  return Boolean(verdict && verdict.opaque)
}

async function checkedCard(key, workFile, notes) {
  let report = await filer(workFile)
  let opaqueAsked = false
  for (let round = 0; round < MAX_CARD_ROUNDS; round++) {
    if (!report) return aside('file', 'pdf-filer stopped before its report twice')
    if (report.unestablished.length) return aside('file', `pdf-filer could not establish the ${report.unestablished.join(', ')}`)
    const card = await drive({ stage: 'file', script: 'file', step: 'drive-card', target: key })
    if (card.state === 'redo-card') {
      report = await filer(workFile, `The draft card lacks fields its item type needs; record them: ${card.missing.join(', ')}`)
    } else if (card.state !== 'card-ok') {
      return { stage: 'file', ...card }
    } else if (report.title_opaque || opaqueAsked || !(await isOpaque(card.title))) {
      notes.push(...report.uncertain.map(field => `recorded with doubt: ${field}`))
      return card
    } else {
      opaqueAsked = true
      report = await filer(workFile, `The main title "${card.title}" is made of nothing but the names of persons: apply "Opaque titles".`)
    }
  }
  return aside('file', `no checked draft card after ${MAX_CARD_ROUNDS} rounds`)
}

async function file(key, workFile, notes) {
  const card = await checkedCard(key, workFile, notes)
  if (card.state !== 'card-ok') return card
  const filed = await drive({ stage: 'file', script: 'file', step: 'drive-file', target: key, onLock: onZotero })
  return { stage: 'file', ...filed }
}

function extractDrive(step, key, extra) {
  if (!ENGINE_STEPS.has(step)) return drive({ stage: 'extract', script: 'extract', step, target: key, extra })
  const flags = step === 'drive-prep' && ARGS.cleanup ? [extra, CLEANUP_FLAG].filter(Boolean).join(' ') : extra
  return onEngine(() => engineTurn(step, key, flags), engineRank(step, key))
}

function cleanUp(parts) {
  return Promise.all(parts.map(part => worker('extract', `Correction listing: ${part.listing}\nWrite your corrections file to: ${part.verdicts}`,
    { label: 'layout corrector', agentType: 'layout-corrector', model: SONNET })))
}

async function engineTurn(step, key, extra) {
  let line = await drive({ stage: 'extract', script: 'extract', step, target: key, extra })
  while (line.state === 'running') line = await drive({ stage: 'extract', script: 'extract', step: 'drive-wait', target: key })
  return line
}

function numbered(dir, files) {
  const names = Object.entries(files).filter(([field]) => field !== COUNT_FIELD)
  return Array.from({ length: files[COUNT_FIELD] }, (_, index) => Object.fromEntries(
    names.map(([field, name]) => [field, `${dir}/${name.replaceAll(NUMBER_SLOT, String(index + 1))}`])))
}

function scope(parts, note, noteKind) {
  return Promise.all(parts.map(part => {
    const lines = [`Scope listing: ${part.listing}`, `Write your verdicts file to: ${part.verdicts}`]
    if (note) lines.push(`${SCOPE_NOTE_OPENING[noteKind]}\n${note}`)
    return worker('extract', lines.join('\n'), { label: 'section scoper', agentType: 'section-scoper', model: SONNET })
  }))
}

function readPages(batches) {
  return Promise.all(batches.map(batch => settledWorker('extract',
    `Pages listing: ${batch.listing}\nWrite the readings file to: ${batch.readings}`,
    { label: 'page reader', agentType: 'page-reader', model: SONNET })))
}

function unsettledReading(repaired) {
  if (!repaired.force_ocr) return ''
  return repaired.pixel_pages ? `${PIXEL_PAGES_FLAG} ${repaired.pixel_pages}` : PIXELS_ONLY_FLAG
}

function checkedFonts(pixelsOnly) {
  return pixelsOnly ? `${FONTS_CHECKED_FLAG} ${PIXELS_ONLY_FLAG}` : FONTS_CHECKED_FLAG
}

async function prepared(key, notes, cleaned, pixelsOnly) {
  if (cleaned) return extractDrive('drive-prep', key, checkedFonts(pixelsOnly))
  const line = await extractDrive('drive-prep', key)
  if (line.state !== 'fonts') return line
  const repaired = await repairFonts(key)
  if (repaired.state !== 'bookmark') return { pdf: line.pdf, ...repaired }
  notes.push(...(repaired.notes || []))
  const recorded = await extractDrive('drive-fonts-checked', key, unsettledReading(repaired))
  if (recorded.state !== FONTS_CHECKED_STATE) return { pdf: line.pdf, ...recorded }
  return extractDrive('drive-prep', key)
}

async function bookmarkedFiled(key, workFile, unbookmarked, notes) {
  const bookmarked = await bookmark(libraryPdfLine(workFile), unbookmarked.kind, unbookmarked.pixels_only)
  if (bookmarked.state !== 'bookmarked') return { pdf: unbookmarked.pdf, ...bookmarked, stage: 'extract' }
  notes.push(...bookmarked.unfound.map(entry => `not found for the outline: ${entry}`))
  if (!bookmarked.divided) notes.push('the bookmarker found no heading: extracted as one chapter')
  const line = await extractDrive('drive-prep', key, bookmarked.divided ? '' : ONE_CHAPTER_FLAG)
  if (line.state !== 'unbookmarked') return line
  return { ...line, state: 'aside', question: `${line.question}, after pdf-bookmarker wrote one` }
}

async function carry(key, workFile, notes, preparation) {
  let line = await prepared(key, notes, preparation.cleaned, preparation.pixelsOnly)
  if (line.state === 'unbookmarked') line = await bookmarkedFiled(key, workFile, line, notes)
  const pdf = line.pdf
  for (let loop = 0; loop < MAX_LOOPS; loop++) {
    if (SCOPE_DISPATCH_STATES.has(line.state)) {
      await scope(numbered(line.dir, line.parts), line.note, 'rescope')
      line = await extractDrive('drive-trial', key)
    } else if (line.state === 'doubtful') {
      const batches = numbered(line.dir, line.batches)
      await readPages(batches)
      line = await writtenOnRedispatch(() => extractDrive('drive-retrial', key), () => readPages(batches))
    } else if (line.state === 'cleanup' || line.state === 'recleanup') {
      await cleanUp(numbered(line.dir, line.parts))
      line = await extractDrive('drive-cleanup', key)
    } else {
      return { stage: 'extract', pdf: line.pdf || pdf, ...line }
    }
  }
  return { stage: 'extract', pdf, state: 'aside', question: `no outcome after ${MAX_LOOPS} steps; last state ${line.state}` }
}

async function cite(key) {
  const linked = await drive({ stage: 'cite', script: 'ingest', step: 'drive-cite', target: key, onLock: onCitations })
  return { stage: 'cite', ...linked }
}

async function classify(key, workFile) {
  const prepared = await drive({ stage: 'classify', script: 'bibliographies', step: 'drive-classify', target: key })
  if (prepared.state !== 'classify') return { stage: 'classify', ...prepared }
  const classifier = () => settledWorker('classify', `Work file: ${workFile}; its basename names the work.\nWrite your answers file to: ${prepared.answers}`,
    { label: 'work classifier', agentType: 'work-classifier', model: SONNET })
  await classifier()
  const placed = await writtenOnRedispatch(() => drive({ stage: 'classify', script: 'bibliographies', step: 'drive-classify', target: key,
    extra: `--answers ${quoted(prepared.answers)}`, onLock: onBibliographies }), classifier)
  return { stage: 'classify', ...placed }
}

async function carryWork(work, byKey) {
  const notes = []
  const key = work.key
  const workFile = workFileOf(byKey, key)
  const start = STAGES.indexOf(work.from)
  let pixelsOnly = false
  if (start <= STAGES.indexOf('clean')) {
    const cleaned = await onCleaning(() => clean(key, workFile, notes))
    if (cleaned.state !== 'file') return { ...cleaned, notes }
    pixelsOnly = cleaned.pixels_only
  }
  if (start <= STAGES.indexOf('file')) {
    const filed = await file(key, workFile, notes)
    if (filed.state !== 'filed') return { ...filed, notes }
  }
  if (start <= STAGES.indexOf('extract')) {
    const extracted = await carry(key, workFile, notes, { cleaned: FROM === 'clean', pixelsOnly })
    if (extracted.state !== 'accepted') return { ...extracted, notes }
    notes.push(...(extracted.notes || []))
  }
  if (start <= STAGES.indexOf('cite')) {
    const linked = await cite(key)
    if (linked.state !== 'linked') return { ...linked, notes }
  }
  const classified = await classify(key, workFile)
  return { ...classified, notes: [...notes, ...(classified.notes || [])] }
}

function batchOptions() {
  const options = [`--from ${FROM}`]
  if (ARGS.start) options.push(`--start ${ARGS.start}`)
  if (ARGS.end) options.push(`--end ${ARGS.end}`)
  if (ARGS.works && ARGS.works.length) options.push(`--works ${ARGS.works.join(' ')}`)
  return options.join(' ')
}

function listedWorks(listed) {
  const stages = listed.stages || {}
  return STAGES.flatMap(stage => (stages[stage] || []).map(key => ({ key, from: stage })))
}

async function batchWorks() {
  const listed = await drive({ stage: 'preflight', script: 'ingest', step: 'drive-batch', extra: batchOptions() })
  if (listed.state !== 'batch') return { byKey: '', works: [] }
  const works = listedWorks(listed)
  Object.entries(listed.costs || {}).forEach(([key, cost]) => workCosts.set(key, cost))
  if (works.length !== listed.count && !halt) halt = `drive-batch listed ${listed.count} works, and ${works.length} came back: run the batch again`
  return { byKey: listed.by_key, works }
}

function convertAhead(works) {
  const keys = works.filter(work => work.from === 'extract').map(work => work.key)
  if (FROM !== 'extract' || !keys.length) return Promise.resolve(null)
  const command = `${SCRIPTS.extract} prefetch ${AWAIT_FONTS_FLAG} --keys ${keys.join(' ')}`
  return drive({ stage: 'extract', script: 'ingest', step: 'drive-detach', target: PREFETCH_KEY, extra: `-- ${command}` })
    .catch(error => error instanceof Paused ? null : { state: 'aside', question: String(error) })
}

function convertAheadQuestions(started) {
  if (!started || started.state === 'running') return []
  return [`the conversion ahead of the run did not start: ${started.question}`]
}

async function carryOne(work, byKey) {
  const outcome = await carryWork(work, byKey).catch(error => error instanceof Paused
    ? { stage: error.stage, state: 'paused' }
    : { stage: work.from, state: 'aside', question: `the workflow failed: ${error}` })
  const settled = outcome.state === 'halt' ? { ...outcome, state: 'paused' } : outcome
  log(`work ${work.key}: ${settled.state}`)
  return { key: work.key, ...settled }
}

async function carryAll(works, byKey) {
  const outcomes = await parallel(works.map(work => () => carryOne(work, byKey)))
  return outcomes.filter(Boolean)
}

function tailStep(step) {
  return drive({ stage: 'tail', script: 'ingest', step })
}

async function glossOne(root, number) {
  const dir = `${root}/${number}`
  await worker('gloss', `Listing: ${dir}/listing.json\nWrite your answers file to: ${dir}/answers.json`,
    { label: 'bibliography introducer', agentType: 'bibliography-introducer', model: SONNET })
  return onBibliographies(() => drive({ stage: 'gloss', script: 'ingest', step: 'drive-gloss-finish', target: dir }))
}

async function gloss(keys) {
  if (ARGS.gloss === 'none') return { glossed: [], questions: [] }
  const extra = ARGS.gloss === 'all' ? '--all' : keys.join(' ')
  const planned = await onBibliographies(() => drive({ stage: 'gloss', script: 'ingest', step: 'drive-gloss-plan', extra }))
  if (planned.state !== 'gloss') return { glossed: [], questions: planned.question ? [planned.question] : [] }
  const numbers = Array.from({ length: planned.count }, (_, index) => index + 1)
  const settled = await parallel(numbers.map(number => () => glossOne(planned.root, number)))
  const outcomes = settled.map(outcome => outcome ?? { state: 'aside', question: 'the gloss run for a bibliography failed' })
  return {
    glossed: outcomes.filter(outcome => outcome.state === 'glossed').map(outcome => outcome.bibliography),
    questions: outcomes.filter(outcome => outcome.state !== 'glossed').map(outcome => `a bibliography was not glossed: ${outcome.question}`),
  }
}

async function judgedCitations(swept) {
  if (swept.state !== 'judge') return swept
  await parallel(Array.from({ length: swept.count }, (_, index) => () => worker('tail',
    `Listing: ${swept.root}/${index + 1}/listing.json\nWrite your answers file to: ${swept.root}/${index + 1}/answers.json`,
    { label: 'citation judge', agentType: 'citation-judge', model: SONNET })))
  const settled = await onCitations(() => tailStep('drive-settle'))
  return { ...settled, questions: [...(swept.questions || []), ...(settled.questions || [])] }
}

async function reshaped() {
  const listed = await drive({ stage: 'shape', script: 'ingest', step: 'drive-clusters' })
  if (listed.state !== 'shape') return { reshaped: null, questions: listed.question ? [listed.question] : [] }
  await parallel(numbered(listed.dir, listed.parts).map(part => () => worker('shape',
    `Listing: ${part.listing}\nWrite your answers file to: ${part.answers}`,
    { label: 'bibliography shaper', agentType: 'bibliography-shaper', model: SONNET })))
  const merged = await drive({ stage: 'shape', script: 'ingest', step: 'drive-merge' })
  if (merged.state !== 'merged') return { reshaped: null, questions: [`the bibliographies were not reshaped: ${merged.question}`] }
  const done = await onBibliographies(() => drive({ stage: 'shape', script: 'ingest', step: 'drive-reshape', target: merged.answers }))
  if (done.unread) return { reshaped: null, questions: [unreadReshaping(listed.outcome, done.question)] }
  if (done.state !== 'reshaped') return { reshaped: null, questions: [`the bibliographies were not reshaped: ${done.question}`] }
  const { created, moved, linked, unlinked, added, folded } = done
  return { reshaped: { created, moved, linked, unlinked, added, folded }, questions: done.questions || [] }
}

function unreadReshaping(outcome, question) {
  return `the reshaping's line was not read, so whether it was applied is unknown: if ${outcome} exists, it holds what the reshaping did; ${question}`
}

async function checkedOff() {
  const read = await tailStep('drive-readings')
  if (read.state !== 'read') return { checked_off: [], questions: [`the project reading lists were not read: ${read.question}`] }
  return { checked_off: read.checked_off || [], questions: read.questions || [] }
}

async function tail(keys) {
  const questions = []
  try {
    const [checked, linked] = await Promise.all([tailStep('drive-check'), tailStep('drive-cite').then(judgedCitations)])
    questions.push(...(checked.questions || []), ...(linked.questions || []))
    const shaped = await reshaped()
    questions.push(...shaped.questions)
    const read = await checkedOff()
    questions.push(...read.questions)
    const glossed = await gloss(keys)
    questions.push(...glossed.questions)
    const indexed = await synced()
    questions.push(...(indexed.questions || []))
    return { questions, reshaped: shaped.reshaped, checked_off: read.checked_off, glossed: glossed.glossed }
  } catch (error) {
    if (!(error instanceof Paused)) questions.push(`the tail failed: ${error}`)
  }
  return { questions, reshaped: null, checked_off: [], glossed: [] }
}

async function synced() {
  if (ARGS.index === false) return { questions: [] }
  let indexed = await index()
  if (indexed.state === 'rebuild') {
    await detached('tail', TAIL_KEY, `${SCRIPTS.search} sync --rebuild`)
    indexed = await index()
    if (indexed.state === 'rebuild' && !halt) halt = indexed.question
  }
  return indexed
}

function index() {
  return detached('tail', TAIL_KEY, `${SCRIPTS.ingest} drive-index`)
}

async function release() {
  const released = await relay(`${SCRIPTS.ingest} drive-release`, 'drive-release', PHASE_OF.tail, RELAY_ATTEMPTS)
  return released.question ? [released.question] : []
}

function report(outcomes, tailed) {
  const settled = state => outcomes.filter(outcome => outcome.state === state)
  return {
    halt,
    paused: settled('paused'),
    filed: settled('placed'),
    set_aside: outcomes.filter(outcome => !['paused', 'placed', 'skip'].includes(outcome.state)),
    skipped: settled('skip'),
    reshaped: tailed.reshaped,
    checked_off: tailed.checked_off,
    glossed: tailed.glossed,
    questions: tailed.questions,
  }
}

const EMPTY_TAIL = { questions: [], reshaped: null, checked_off: [], glossed: [] }

function placedKeys(outcomes) {
  return outcomes.filter(outcome => outcome.state === 'placed').map(outcome => outcome.key)
}

async function carryBatch() {
  const { byKey, works } = await batchWorks()
  if (works.length > WORKS_PER_RUN[FROM]) log(`${works.length} works in one run: a run SHOULD carry at most ${WORKS_PER_RUN[FROM]}; pass start and end`)
  const ahead = halt ? Promise.resolve(null) : convertAhead(works)
  const outcomes = halt ? [] : await carryAll(works, byKey)
  const aheadQuestions = convertAheadQuestions(await ahead)
  phase('Tail')
  const tailed = halt ? EMPTY_TAIL : await tail(placedKeys(outcomes))
  return { outcomes, tailed: { ...tailed, questions: [...aheadQuestions, ...tailed.questions] } }
}

phase('Preflight')
await drive({ stage: 'preflight', script: 'ingest', step: 'preflight', extra: `--from ${FROM}` })
if (halt) return report([], EMPTY_TAIL)
let carried = { outcomes: [], tailed: EMPTY_TAIL }
try {
  carried = await carryBatch()
} finally {
  carried.tailed = { ...carried.tailed, questions: [...carried.tailed.questions, ...(await release())] }
}
return report(carried.outcomes, carried.tailed)
