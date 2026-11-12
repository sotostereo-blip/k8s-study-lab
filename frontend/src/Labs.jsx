import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { EnglishBar, EnglishText } from './english.jsx'

/* Hands-on labs: pick a task, a real k3s cluster starts in Docker, solve it in the browser terminal. */

export default function Labs({ trackId }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [openId, setOpenId] = useState(null)
  const [domain, setDomain] = useState('')
  const [mock, setMock] = useState(null)         // mock exam open on screen
  const [pendingMock, setPendingMock] = useState(null)  // unfinished mock exam, can be resumed

  const reload = () => Promise.all([api.labs(trackId), api.mockCurrent(trackId)])
    .then(([d, m]) => { setData(d); setPendingMock(m); setError(null) })
    .catch((e) => setError(e.message))
  useEffect(() => { reload() }, [])

  if (error) return <p className="error">Cannot load labs: {error}</p>
  if (!data) return <p>Loading…</p>

  const track = data.tracks[0]
  const domains = Object.fromEntries(track.domains.map((d) => [d.id, d]))
  const running = data.lab.status !== 'idle' ? data.tasks.find((t) => t.id === data.lab.task_id) : null

  if (mock) return <MockExam session={mock} track={track} domains={domains} onExit={() => { setMock(null); reload() }} />

  if (openId) {
    const task = data.tasks.find((t) => t.id === openId)
    return <LabView task={task} track={track} domainName={domains[task.domain].name}
      onBack={() => { setOpenId(null); reload() }} />
  }

  const list = data.tasks.filter((t) => !domain || t.domain === domain)
  const solved = data.tasks.filter((t) => t.progress?.solved).length

  return (
    <section>
      <h1>Hands-on labs</h1>
      <p className="sub">
        Practice for the {track.name} exam. Choosing a lab starts {introOf(track)} with
        a terminal in your browser. Solve the task, then press <b>Check my work</b>.
        · {solved}/{data.tasks.length} solved
      </p>
      {track.mock && <MockPanel trackId={trackId} passing={track.passing_score} history={data.mock_exams} pending={pendingMock} onOpen={setMock} onAbandoned={reload}
        busy={data.lab.status === 'starting' || data.lab.status === 'ready'} />}
      {running && (
        <div className="banner">
          <span>Running now: <b>{running.title}</b> ({data.lab.status})</span>
          <button className="primary" onClick={() => setOpenId(running.id)}>Open</button>
        </div>
      )}
      <div className="chips">
        <button className={!domain ? 'active' : ''} onClick={() => setDomain('')}>All ({data.tasks.length})</button>
        {track.domains.map((d) => {
          const n = data.tasks.filter((t) => t.domain === d.id).length
          return <button key={d.id} className={domain === d.id ? 'active' : ''} onClick={() => setDomain(d.id)}>
            {d.name} · {d.weight}% ({n})
          </button>
        })}
      </div>
      <div className="lab-grid">
        {list.map((t) => (
          <button key={t.id} className={`lab-card ${t.progress?.solved ? 'solved' : ''}`} onClick={() => setOpenId(t.id)}>
            <span className="lab-domain">{domains[t.domain].name}</span>
            <strong>{t.title}</strong>
            <span className="lab-meta">
              <span>{'●'.repeat(t.difficulty)}{'○'.repeat(3 - t.difficulty)}</span>
              <span>{t.minutes} min</span>
              <span className="env">{envLabel(track.environments[t.environment])}</span>
            </span>
            <span className="lab-progress">
              {t.progress?.solved ? `✓ Solved${t.progress.best_seconds ? ` in ${fmt(t.progress.best_seconds)}` : ''}`
                : t.progress ? `${t.progress.tries} tries` : 'Not tried'}
            </span>
          </button>
        ))}
      </div>
    </section>
  )
}

function LabView({ task, track, domainName, onBack }) {
  const [lab, setLab] = useState(null)
  const [result, setResult] = useState(null)
  const [checking, setChecking] = useState(false)
  const [solution, setSolution] = useState(null)
  const [now, setNow] = useState(Date.now())
  const [frameKey, setFrameKey] = useState(0)
  const readyAt = useRef(null)

  const mine = lab && lab.task_id === task.id
  const status = mine ? lab.status : 'idle'

  const start = async () => {
    setResult(null); setSolution(null); readyAt.current = null
    setLab(await api.labStart(task.id))
  }

  // Start automatically when the lab is opened (unless it is already running).
  useEffect(() => {
    let cancelled = false
    api.labStatus().then((s) => {
      if (cancelled) return
      if (s.task_id === task.id && s.status !== 'error') { setLab(s); return }
      if (s.status === 'starting' || s.status === 'ready') {
        const other = s.task_id
        const what = other?.startsWith('mock-') ? 'Your mock exam is running' : `Another lab (${other}) is running`
        if (!window.confirm(`${what}. Stop it and start this lab?`)) { onBack(); return }
      }
      start()
    })
    return () => { cancelled = true }
  }, [task.id])

  // Poll while the cluster is starting.
  useEffect(() => {
    if (status !== 'starting' && status !== 'stopping') return
    const t = setInterval(() => api.labStatus().then(setLab), 1500)
    return () => clearInterval(t)
  }, [status])

  // Exam-style timer.
  useEffect(() => {
    if (status !== 'ready') return
    readyAt.current ??= Date.now() - (lab.elapsed_seconds || 0) * 1000
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [status])

  const check = async () => {
    setChecking(true)
    try { setResult(await api.labCheck(task.id)) } catch (e) { setResult({ error: e.message }) }
    setChecking(false)
  }
  const stop = async () => { setLab({ ...lab, status: 'stopping' }); await api.labStop(); onBack() }

  const elapsed = readyAt.current ? Math.round((now - readyAt.current) / 1000) : 0
  const over = elapsed > task.minutes * 60
  const checkState = (name) => result?.checks?.find((c) => c.name === name)

  return (
    <section className="lab-view">
      <div className="lab-side">
        <button className="link" onClick={onBack}>← All labs</button>
        <div className="meta"><span>{domainName}</span><span>{'●'.repeat(task.difficulty)}{'○'.repeat(3 - task.difficulty)}</span><span>{track.environments[task.environment].name}</span></div>
        <h1>{task.title}</h1>
        {status === 'ready' && (
          <p className={`timer ${over ? 'low' : ''}`}>{fmt(elapsed)} <small>/ {task.minutes}:00 target</small></p>
        )}
        <div className="task-text"><Markdown text={task.task} /></div>
        <EnglishBar text={`${task.title}\n${noCode(task.task)}`} speakText={`${task.title}. ${speakable(task.task)}`} />

        <h2>Checks</h2>
        <ul className="checks">
          {task.checks.map((name) => {
            const c = checkState(name)
            return (
              <li key={name} className={c ? (c.passed ? 'pass' : 'fail') : ''}>
                <span className="mark">{c ? (c.passed ? '✓' : '✗') : '○'}</span>
                <span><Inline text={name} />{c && !c.passed && c.output && <code className="out">{c.output}</code>}</span>
              </li>
            )
          })}
        </ul>
        {result?.solved && <p className="feedback ok"><strong>Solved!</strong> All checks passed in {fmt(result.seconds || 0)}.</p>}
        {result?.error && <p className="error">{result.error}</p>}

        <div className="actions">
          <button className="primary" disabled={status !== 'ready' || checking} onClick={check}>{checking ? 'Checking…' : 'Check my work'}</button>
          <button disabled={status === 'starting' || status === 'stopping'} onClick={start}>Reset lab</button>
          <button disabled={status === 'idle' || status === 'stopping'} onClick={stop}>Stop lab</button>
        </div>
        <div className="actions">
          {solution
            ? <div className="solution"><pre>{solution.solution}</pre>
              <p className="docs">Docs: {solution.docs.map((d) => <a key={d} href={d} target="_blank" rel="noreferrer">{d.replace(/^https?:\/\//, '')}</a>)}</p></div>
            : <button className="link" onClick={() => api.labSolution(task.id).then(setSolution)}>Show solution</button>}
        </div>
      </div>

      <div className="lab-terminal">
        {status === 'ready' && lab.terminal_url ? (
          <>
            <div className="term-bar">
              <span>Terminal · <Inline text={toolsOf(track.environments[task.environment])} /></span>
              <span>
                <button className="link" onClick={() => setFrameKey(frameKey + 1)}>Reconnect</button>
                {' · '}
                <a href={lab.terminal_url} target="_blank" rel="noreferrer">Open in new tab</a>
              </span>
            </div>
            <iframe key={frameKey} title="lab terminal" src={lab.terminal_url} />
          </>
        ) : (
          <div className="term-wait">
            {status === 'error' ? <p className="error">{lab.error}</p>
              : <p><span className="spinner" /> {status === 'stopping' ? 'Stopping the lab…' : 'Starting your cluster…'}</p>}
            <pre>{(lab?.log || []).join('\n')}</pre>
            {status === 'error' && <button className="primary" onClick={start}>Try again</button>}
          </div>
        )}
      </div>
    </section>
  )
}

/* ---------- tiny Markdown: paragraphs, lists, `code`, **bold** ---------- */

function Markdown({ text }) {
  const blocks = text.trim().split(/\n\s*\n/)
  return blocks.map((b, i) => {
    const lines = b.split('\n')
    const items = []
    for (const line of lines) {
      const m = line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)$/)
      if (m) items.push({ text: m[1], sub: /^\s{2,}/.test(line), ordered: /^\s*\d+\./.test(line) })
      else if (items.length) items[items.length - 1].text += ' ' + line.trim()
      else items.push({ text: line, plain: true })
    }
    if (items.every((it) => it.plain)) return <p key={i}><Inline text={items.map((it) => it.text).join(' ')} /></p>
    const intro = items.filter((it) => it.plain)
    const listItems = items.filter((it) => !it.plain)
    const Tag = listItems[0]?.ordered ? 'ol' : 'ul'
    return (
      <div key={i}>
        {intro.length > 0 && <p><Inline text={intro.map((it) => it.text).join(' ')} /></p>}
        <Tag>{listItems.map((it, k) => <li key={k} className={it.sub ? 'sub' : ''}><Inline text={it.text} /></li>)}</Tag>
      </div>
    )
  })
}

function Inline({ text }) {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g)
  return parts.map((p, i) =>
    p.startsWith('`') ? <code key={i}>{p.slice(1, -1)}</code>
      : p.startsWith('**') ? <strong key={i}><EnglishText text={p.slice(2, -2)} /></strong>
        : <EnglishText key={i} text={p} />)
}

/* key words should not come from names inside `code` (gpu-job is not the word Job) */
const noCode = (md) => md.replace(/`[^`]+`/g, ' ')

/* text for the 🔊 button: no Markdown, no YAML/commands in backticks read letter by letter */
const speakable = (md) => md.replace(/`([^`]+)`/g, '$1').replace(/\*\*/g, '').replace(/^\s*[-*]\s+/gm, '').replace(/\n+/g, ' ')

function fmt(s) {
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

/* ---------- Mock exam: several tasks in one cluster, one timer, scored at the end ---------- */

function MockPanel({ trackId, passing, history, pending, onOpen, onAbandoned, busy }) {
  const [count, setCount] = useState(10)
  const [starting, setStarting] = useState(false)
  const start = async () => {
    setStarting(true)
    try { onOpen(await api.mockStart(trackId, count)) } finally { setStarting(false) }
  }
  return (
    <div className="mock-panel">
      <div>
        <h2>Mock exam</h2>
        <p className="sub">
          Several tasks in one lab environment with one timer, like the real exam. You only see your
          score at the end (partial credit per task). Pass mark: {passing}%.
        </p>
        {history.length > 0 && (
          <p className="history">Last scores: {history.map((h) => (
            <span key={h.id} className={h.score >= passing ? 'ok' : 'ko'}>{h.score}%</span>
          ))}</p>
        )}
      </div>
      <div className="mock-actions">
        {pending ? (
          <>
            <button className="primary" onClick={() => onOpen(pending)}>Resume mock exam ({pending.tasks.length} tasks)</button>
            <button className="link" onClick={async () => { await api.mockAbandon(pending.session_id); onAbandoned() }}>
              Abandon it
            </button>
          </>
        ) : (
          <>
            <label>Tasks
              <select value={count} onChange={(e) => setCount(+e.target.value)}>
                <option value={5}>5 tasks</option>
                <option value={10}>10 tasks</option>
                <option value={15}>15 tasks (about as long as the real exam)</option>
              </select>
            </label>
            <button className="primary" disabled={starting} onClick={start}>{starting ? 'Starting…' : 'Start mock exam'}</button>
            {busy && <small className="sub">This stops the lab that is running now.</small>}
          </>
        )}
      </div>
    </div>
  )
}

function MockExam({ session, track, domains, onExit }) {
  const [lab, setLab] = useState(session.lab)
  const [i, setI] = useState(0)
  const [flags, setFlags] = useState({})
  const [now, setNow] = useState(Date.now())
  const [result, setResult] = useState(null)
  const [grading, setGrading] = useState(false)
  const [error, setError] = useState(null)
  const [frameKey, setFrameKey] = useState(0)
  const [confirming, setConfirming] = useState(null)  // 'finish' | 'abandon'
  const readyAt = useRef(null)
  const submitted = useRef(false)
  const status = lab?.status || 'idle'
  const total = session.minutes * 60

  useEffect(() => {
    if (status === 'ready' || result) return
    const t = setInterval(() => api.labStatus().then((s) => {
      if (s.task_id === `mock-${session.session_id}`) setLab(s)
      else setLab({ ...s, status: 'idle' })
    }), 1500)
    return () => clearInterval(t)
  }, [status, result])

  useEffect(() => {
    if (status !== 'ready' || result) return
    readyAt.current ??= Date.now() - (lab.elapsed_seconds || 0) * 1000
    setNow(Date.now())
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [status, result])

  const elapsed = readyAt.current ? Math.round((now - readyAt.current) / 1000) : 0
  const left = Math.max(0, total - elapsed)

  const submit = async () => {
    if (submitted.current) return
    submitted.current = true
    setConfirming(null)
    setGrading(true); setError(null)
    try { setResult(await api.mockSubmit(session.session_id)) } catch (e) { setError(e.message); submitted.current = false }
    setGrading(false)
  }
  useEffect(() => { if (status === 'ready' && readyAt.current && left === 0 && !result) submit() }, [left])

  if (result) return <MockResult result={result} domains={domains} onExit={onExit} />

  const task = session.tasks[i]
  return (
    <section className="lab-view">
      <div className="lab-side">
        <button className="link" onClick={onExit}>← Labs (the exam keeps running)</button>
        <div className="mock-head">
          <span className={`timer ${left < 300 && status === 'ready' ? 'low' : ''}`}>
            {status === 'ready' ? fmt(left) : '--:--'}
          </span>
          <small>{session.minutes} min · {session.tasks.length} tasks · pass {session.passing_score}%</small>
        </div>
        <div className="dots">
          {session.tasks.map((t, k) => (
            <button key={t.id} className={[k === i && 'cur', flags[t.id] && 'flag'].filter(Boolean).join(' ')}
              onClick={() => setI(k)} title={t.title}>{k + 1}</button>
          ))}
        </div>
        <div className="meta">
          <span>Task {i + 1} of {session.tasks.length}</span>
          <span>{domains[task.domain].name}</span>
          <span>{task.points} points</span>
        </div>
        <h1>{task.title}</h1>
        <div className="task-text"><Markdown text={task.task} /></div>
        <EnglishBar key={task.id} text={`${task.title}\n${noCode(task.task)}`} speakText={`${task.title}. ${speakable(task.task)}`} />
        <div className="actions">
          <button disabled={i === 0} onClick={() => setI(i - 1)}>Previous</button>
          <button disabled={i === session.tasks.length - 1} onClick={() => setI(i + 1)}>Next</button>
          <button onClick={() => setFlags({ ...flags, [task.id]: !flags[task.id] })}>
            {flags[task.id] ? '★ Flagged' : '☆ Flag for review'}
          </button>
        </div>
        {confirming ? (
          <div className="confirm">
            <p>{confirming === 'finish'
              ? `Finish the exam and grade all tasks now?${Object.values(flags).some(Boolean) ? ' You still have flagged tasks.' : ''}`
              : 'Abandon this mock exam? It will not be scored and the cluster stops.'}</p>
            <div className="actions">
              <button className="primary" onClick={confirming === 'finish' ? submit
                : async () => { await api.mockAbandon(session.session_id); onExit() }}>
                {confirming === 'finish' ? 'Yes, finish and grade' : 'Yes, abandon'}
              </button>
              <button onClick={() => setConfirming(null)}>Cancel</button>
            </div>
          </div>
        ) : (
          <div className="actions">
            <button className="primary" disabled={status !== 'ready' || grading} onClick={() => setConfirming('finish')}>
              {grading ? 'Grading all tasks… (about a minute)' : 'Finish exam'}
            </button>
            <button className="link" disabled={grading} onClick={() => setConfirming('abandon')}>Abandon</button>
          </div>
        )}
        {error && <p className="error">{error}</p>}
      </div>

      <div className="lab-terminal">
        {status === 'ready' && lab.terminal_url ? (
          <>
            <div className="term-bar">
              <span>Exam terminal · all tasks share this cluster</span>
              <span>
                <button className="link" onClick={() => setFrameKey(frameKey + 1)}>Reconnect</button>
                {' · '}
                <a href={lab.terminal_url} target="_blank" rel="noreferrer">Open in new tab</a>
              </span>
            </div>
            <iframe key={frameKey} title="exam terminal" src={lab.terminal_url} />
          </>
        ) : (
          <div className="term-wait">
            {status === 'error' ? <p className="error">{lab.error}</p>
              : status === 'idle' ? <p className="error">The exam cluster is not running (Docker or the backend was restarted). Abandon this exam and start a new one.</p>
                : <p><span className="spinner" /> Preparing the exam cluster and all {session.tasks.length} scenarios… (2–4 min). The timer starts when it is ready.</p>}
            <pre>{(lab?.log || []).join('\n')}</pre>
          </div>
        )}
      </div>
    </section>
  )
}

function MockResult({ result, domains, onExit }) {
  const [stopping, setStopping] = useState(false)
  const solved = result.tasks.filter((t) => t.solved).length
  return (
    <section>
      <h1>{result.score}% — {result.passed ? 'Pass' : 'Not yet'}</h1>
      <p className="sub">
        {solved}/{result.tasks.length} tasks fully solved · pass mark {result.passing_score}% ·
        time used {fmt(result.elapsed_seconds || 0)} of {result.minutes}:00{result.overtime ? ' (over time)' : ''}
      </p>
      <table>
        <thead><tr><th>#</th><th>Task</th><th>Domain</th><th>Points</th><th></th></tr></thead>
        <tbody>
          {result.tasks.map((t, k) => (
            <tr key={t.task_id}>
              <td>{k + 1}</td><td>{t.title}</td><td>{domains[t.domain].name}</td>
              <td>{t.earned}/{t.points}</td>
              <td><div className="bar"><i style={{ width: `${(100 * t.earned) / t.points}%` }} /></div></td>
            </tr>
          ))}
        </tbody>
      </table>
      <h2>Review</h2>
      {result.tasks.map((t, k) => (
        <details key={t.task_id} className={`review ${t.solved ? 'ok' : 'ko'}`}>
          <summary>{k + 1}. {t.solved ? '✓' : '✗'} {t.title} — {t.earned}/{t.points}</summary>
          <ul className="checks">
            {t.checks.map((c) => (
              <li key={c.name} className={c.passed ? 'pass' : 'fail'}>
                <span className="mark">{c.passed ? '✓' : '✗'}</span>
                <span><Inline text={c.name} />{c.guard && <small className="guard"> must stay true · no points</small>}
                  {!c.passed && c.output && <code className="out">{c.output}</code>}</span>
              </li>
            ))}
          </ul>
          {!t.guards_ok && <p className="error">A "must stay true" check failed, so this task scores 0.</p>}
          <div className="solution"><pre>{t.solution}</pre>
            <p className="docs">Docs: {t.docs.map((d) => <a key={d} href={d} target="_blank" rel="noreferrer">{d.replace(/^https?:\/\//, '')}</a>)}</p></div>
        </details>
      ))}
      <p className="sub">The cluster is still running, so you can look at what went wrong in the terminal.</p>
      <div className="actions">
        <button className="primary" onClick={onExit}>Back to labs</button>
        <button disabled={stopping} onClick={async () => { setStopping(true); await api.labStop(); onExit() }}>
          {stopping ? 'Stopping…' : 'Stop the cluster'}
        </button>
      </div>
    </section>
  )
}

const introOf = (track) => track.intro
  || (Object.values(track.environments).some((e) => e.nodes > 0) ? 'a real Kubernetes cluster in Docker' : 'a lab environment in Docker')
const envLabel = (env) => env.label || (env.nodes === 0 ? 'Docker' : env.nodes === 1 ? '1 node' : `${env.nodes} nodes`)
const toolsOf = (env) => env.tools || (env.nodes ? 'kubectl is ready (alias `k`)' : 'the lab tools are ready')
