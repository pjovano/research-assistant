export const meta = {
  name: 'resolve-tasks',
  description: 'Accept each atomic note whose accept task is checked, resolve the checked tasks of the atomic notes and research the stub notes: create each further note, research it and each stub with note-researcher, then revise each note the tasks came from with note-reviewer',
  whenToUse: 'the user asks for the checked tasks of the atomic notes to be resolved, or the stub notes to be researched; args {limit} caps the further notes and stubs one run takes, 8 if absent',
  phases: [
    { title: 'Accept', detail: 'notes.py accept: every line marked for review of each note whose accept task is checked takes the accepted mark' },
    { title: 'Find', detail: 'notes.py chosen: the checked tasks, each further note created with its starting claim, and the stub notes' },
    { title: 'Research', detail: 'one note-researcher per further note and per stub note' },
    { title: 'Review', detail: 'one note-reviewer per note whose tasks were resolved, once its further notes are researched' },
    { title: 'Confirm', detail: 'notes.py chosen again: the checked tasks still standing' },
  ],
}

const PYTHON = '~/.research-vault/venv/bin/python'
const NOTES = `${PYTHON} ~/Developer/research-tools/.claude/skills/take-notes/scripts/notes.py`
const DEFAULT_LIMIT = 8
const RELAY_ATTEMPTS = 2
const WORKER_ATTEMPTS = 2
const REPLY_OPENING_CHARS = 300
const REVIEW_STATE = 'review'
const ENRICH_STATE = 'enrich'
const SURROUNDING_BACKTICKS = /^`+|`+$/g

const limit = Number.isInteger(args?.limit) && args.limit > 0 ? args.limit : DEFAULT_LIMIT

phase('Accept')
const acceptance = await relay(`${NOTES} accept --apply`, 'accept', 'Accept')
if (acceptance.error) return acceptance
const accepted = acceptance.accepted

phase('Find')
const found = await relay(`${NOTES} chosen --limit ${limit} --apply`, 'chosen', 'Find')
if (found.error) return { accepted, ...found }
if (found.deferred.length) log(`${distinctTitles(found.deferred).length} further notes wait past the limit of ${limit}`)
if (found.retagged?.length) log(`${found.retagged.length} retagged tasks name no further note yet and stay checked`)
if (found.unparsed.length) log(`${found.unparsed.length} checked lines are in no task form and stay as they are`)
if (found.deferred_stubs.length) log(`${found.deferred_stubs.length} stub notes wait past the limit of ${limit}`)
if (!found.tasks.length && !found.stubs.length) return { accepted, found, research: [], stubs: [], reviews: [], standing: [] }

const research = new Map()
const reviewedNotes = [...new Set(found.tasks.map(task => task.reviewed))]
const [reviews, stubs] = await Promise.all([
  parallel(reviewedNotes.map(note => () => reviewOnceResearched(note))),
  parallel(found.stubs.map(title => () => researchStub(title))),
])

phase('Confirm')
const after = await relay(`${NOTES} chosen --limit ${limit}`, 'chosen again', 'Confirm')
const standingLines = new Set((after.tasks || []).map(task => task.line))
const reports = await Promise.all([...research.values()])
return {
  accepted,
  found: { to_create: found.to_create, deferred: found.deferred, refused: found.refused, unparsed: found.unparsed,
    deferred_stubs: found.deferred_stubs },
  research: reports,
  stubs: stubs.filter(Boolean),
  reviews: reviews.filter(Boolean),
  standing: found.tasks.filter(task => standingLines.has(task.line)),
}

async function reviewOnceResearched(note) {
  const tasks = found.tasks.filter(task => task.reviewed === note)
  const reports = await Promise.all(tasks.map(researchedOnce))
  const resolved = tasks.filter((task, index) => !reports[index].error)
  if (!resolved.length) return { note, skipped: 'no further note of its tasks was researched' }
  return { note, report: await worker(reviewPrompt(note, resolved), 'note-reviewer', `review ${note}`, 'Review') }
}

function researchedOnce(task) {
  if (!research.has(task.title)) research.set(task.title, researchNote(task))
  return research.get(task.title)
}

async function researchNote(task) {
  if (task.state === ENRICH_STATE) return { note: task.title, skipped: 'an enrich task is resolved in its own note by its review' }
  if (task.state === REVIEW_STATE) return { note: task.title, skipped: 'its note already holds references' }
  const report = await worker(researchPrompt(task), 'note-researcher', `research ${task.title}`, 'Research')
  return { note: task.title, ...report }
}

async function researchStub(title) {
  const report = await worker(`Research the atomic note titled: ${title}`, 'note-researcher', `research ${title}`, 'Research')
  return { note: title, ...report }
}

function researchPrompt(task) {
  const reviewed = found.tasks.filter(each => each.title === task.title).map(each => `“${each.reviewed}”`)
  return [
    `Research the atomic note titled: ${task.title}`,
    '',
    `The note resolves a chosen task, and its first claim is the task's claim. The task's line:`,
    task.line,
    '',
    "Start the search from the task's passages.",
    `Write no relation to the reviewed note that chose the task: ${reviewed.join(', ')}.`,
  ].join('\n')
}

function reviewPrompt(note, resolved) {
  return [
    `Review the atomic note titled: ${note}`,
    '',
    'Tasks of it resolved in this operation, each with its thread and its new note:',
    ...resolved.map(task => task.state === ENRICH_STATE
      ? `- thread \`enrich\`, on this note itself. Its line: ${task.line}`
      : `- thread \`${task.thread}\`, new note “${task.title}”. Its line: ${task.line}`),
    '',
    "Delete those lines at step 8, and no other task.",
  ].join('\n')
}

async function worker(prompt, agentType, label, phaseTitle) {
  let reply = ''
  for (let attempt = 1; attempt <= WORKER_ATTEMPTS; attempt++) {
    reply = await agent(prompt, { agentType, label: attempt === 1 ? label : `${label}, dispatched again`, phase: phaseTitle })
    const report = jsonObjectOf(reply)
    if (report && !report.error) return report
  }
  return { error: `${label} returned no report`, reply: String(reply ?? '').slice(0, REPLY_OPENING_CHARS) }
}

async function relay(command, label, phaseTitle) {
  let reply = ''
  for (let attempt = 1; attempt <= RELAY_ATTEMPTS; attempt++) {
    reply = await agent(command, { agentType: 'relay', model: 'haiku', effort: 'low', label, phase: phaseTitle })
    const line = jsonLineOf(reply)
    if (line) return line
  }
  return { error: `${label} returned no JSON line; the command relayed: ${command}`, reply: String(reply ?? '').slice(0, REPLY_OPENING_CHARS) }
}

function jsonLineOf(reply) {
  const lines = String(reply ?? '').trim().split('\n').filter(line => line.trim())
  try {
    return JSON.parse(lines[lines.length - 1].trim().replace(SURROUNDING_BACKTICKS, ''))
  } catch {
    return null
  }
}

function jsonObjectOf(reply) {
  const text = String(reply ?? '')
  try {
    return JSON.parse(text.slice(text.indexOf('{'), text.lastIndexOf('}') + 1))
  } catch {
    return null
  }
}

function distinctTitles(tasks) {
  return [...new Set(tasks.map(task => task.title))]
}
