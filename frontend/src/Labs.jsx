import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'

/* Hands-on labs: pick a task, a real k3s cluster starts in Docker, solve it in the browser terminal. */

export default function Labs() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [openId, setOpenId] = useState(null)
  const [domain, setDomain] = useState('')

  const reload = () => api.labs().then((d) => { setData(d); setError(null) }).catch((e) => setError(e.message))
  useEffect(() => { reload() }, [])

  if (error) return <p className="error">Cannot load labs: {error}</p>
  if (!data) return <p>Loading…</p>

  const track = data.tracks[0]
  const domains = Object.fromEntries(track.domains.map((d) => [d.id, d]))
  const running = data.lab.status !== 'idle' ? data.tasks.find((t) => t.id === data.lab.task_id) : null

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
        Practice for the {track.name} exam. Choosing a lab starts a real Kubernetes cluster in Docker
        with a terminal in your browser. Solve the task, then press <b>Check my work</b>.
        · {solved}/{data.tasks.length} solved
      </p>
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
              <span className="env">{track.environments[t.environment].nodes === 1 ? '1 node' : `${track.environments[t.environment].nodes} nodes`}</span>
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
        if (!window.confirm(`Another lab (${other}) is running. Stop it and start this one?`)) { onBack(); return }
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
              <span>Terminal · kubectl is ready (alias <code>k</code>)</span>
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
      : p.startsWith('**') ? <strong key={i}>{p.slice(2, -2)}</strong>
        : p)
}

function fmt(s) {
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}
