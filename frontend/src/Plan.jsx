import { useEffect, useState } from 'react'
import { api } from './api.js'

const VERDICT = {
  ready: { label: 'Ready', cls: 'ok' },
  almost: { label: 'Almost ready', cls: 'warn' },
  'not-yet': { label: 'Not ready yet', cls: 'ko' },
  unknown: { label: 'Not measured yet', cls: 'muted' },
}
const PHASE = { learn: 'Learn', practice: 'Practice', final: 'Final week', rest: 'Rest', done: 'Done' }
const PACE = { ahead: 'Ahead of plan', 'on-track': 'On track', behind: 'Behind plan' }
const MINUTES = [30, 45, 60, 90, 120, 180]

const fmtDate = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
const isoToday = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10) }

export default function Plan({ cert, onGo }) {
  const [data, setData] = useState(null)
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState(null)
  const load = () => api.plan(cert.id).then((d) => { setData(d); setEditing(!d.goal) }).catch((e) => setError(e.message))
  useEffect(() => { load() }, [cert.id])

  if (error) return <p className="error">{error}</p>
  if (!data) return <p>Loading…</p>
  const save = (body) => api.planSet(cert.id, body).then((d) => { setData(d); setEditing(false); setError(null) })
    .catch((e) => setError(e.message))
  const remove = () => api.planDelete(cert.id).then(load)

  return (
    <section className="plan">
      <h1>Study plan</h1>
      <p className="sub">{cert.name}</p>
      {editing
        ? <GoalForm goal={data.goal} official={cert.official} onSave={save} onCancel={data.goal ? () => setEditing(false) : null} />
        : <GoalLine goal={data.goal} today={data.today} onEdit={() => setEditing(true)} onRemove={remove} />}
      {data.today && <Today today={data.today} goal={data.goal} onGo={onGo} />}
      <Readiness r={data.readiness} onGo={onGo} />
      {data.today?.roadmap?.length > 0 && <Roadmap phases={data.today.roadmap} />}
    </section>
  )
}

function GoalForm({ goal, official, onSave, onCancel }) {
  const [date, setDate] = useState(goal?.exam_date || '')
  const [minutes, setMinutes] = useState(goal?.minutes_per_day || 60)
  return (
    <form className="goal-form card" onSubmit={(e) => { e.preventDefault(); if (date) onSave({ exam_date: date, minutes_per_day: +minutes }) }}>
      <b>When is your exam?</b>
      <p className="muted small">Pick the date you booked, or the date you want to be ready. The plan spreads the
        questions{official?.format?.startsWith('Performance') ? ' and labs' : ''} over the days you have left.</p>
      <div className="goal-fields">
        <label>Exam date <input type="date" required min={isoToday()} value={date} onChange={(e) => setDate(e.target.value)} /></label>
        <label>Time per day
          <select value={minutes} onChange={(e) => setMinutes(e.target.value)}>
            {MINUTES.map((m) => <option key={m} value={m}>{m < 60 ? `${m} minutes` : `${m / 60} hour${m > 60 ? 's' : ''}`}</option>)}
          </select>
        </label>
      </div>
      <div className="actions">
        <button className="primary" type="submit" disabled={!date}>Save my plan</button>
        {onCancel && <button type="button" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  )
}

function GoalLine({ goal, today, onEdit, onRemove }) {
  return (
    <div className="goal-line card">
      <div>
        <b>Exam on {fmtDate(goal.exam_date)}</b>
        <span className="muted"> · {today.days_left >= 0 ? `${today.days_left} day${today.days_left === 1 ? '' : 's'} left` : 'date passed'}
          {' '}· {goal.minutes_per_day} min a day</span>
      </div>
      <div className="goal-buttons">
        <button className="link" onClick={onEdit}>Change</button>
        <button className="link" onClick={onRemove}>Remove</button>
      </div>
    </div>
  )
}

function Today({ today, goal, onGo }) {
  const doneAll = today.items.length > 0 && today.items.every((i) => i.done >= i.target)
  return (
    <>
      <h2>Today <span className={`phase phase-${today.phase}`}>{PHASE[today.phase]}</span></h2>
      <p className="muted small">{today.message}</p>
      {today.pace && (
        <p className={`pace pace-${today.pace.status}`}>
          {PACE[today.pace.status]}: you have tried {today.pace.actual}% of the material; the plan expects {today.pace.expected}% by today.
        </p>
      )}
      {today.items.length === 0
        ? <p>Nothing planned for today.</p>
        : (
          <ul className="today">
            {today.items.map((it, i) => {
              const done = it.done >= it.target
              return (
                <li key={i} className={done ? 'done' : ''}>
                  <span className="check" aria-hidden>{done ? '✓' : '○'}</span>
                  <div className="today-text">
                    <b>{it.title}</b>
                    <span className="muted small">{it.detail}</span>
                    {it.target > 1 && (
                      <span className="bar" title={`${it.done} of ${it.target}`}><i style={{ width: `${(100 * it.done) / it.target}%` }} /></span>
                    )}
                  </div>
                  <span className="mins">{it.minutes} min</span>
                  <button onClick={() => onGo(it.tab, it.domain ? { domain: it.domain } : undefined)}>{done ? 'Open' : 'Start'}</button>
                </li>
              )
            })}
          </ul>
        )}
      <p className="muted small">
        {doneAll ? 'All done for today. Great work!' : `About ${today.minutes} minutes in total (you set ${goal.minutes_per_day}).`}
        {' '}Progress updates as you practise.
      </p>
    </>
  )
}

function Readiness({ r, onGo }) {
  const v = VERDICT[r.verdict]
  return (
    <>
      <h2>Am I ready?</h2>
      <div className="readiness card">
        <div className="score">
          <b>{r.estimate}%</b>
          <span>estimated score</span>
        </div>
        <div className="score-detail">
          <span className={`verdict ${v.cls}`}>{v.label}</span>
          <div className="gauge" aria-label={`Estimated ${r.estimate}%, passing ${r.passing}%`}>
            <i style={{ width: `${r.estimate}%` }} className={v.cls} />
            <em style={{ left: `${r.passing}%` }} title={`Passing score: ${r.passing}%`} />
          </div>
          <span className="muted small">You need {r.passing}% to pass. Confidence: {r.confidence}.</span>
          <p>{r.message}</p>
        </div>
      </div>
      {r.next_steps.length > 0 && (
        <ul className="next-steps">
          {r.next_steps.map((s, i) => <li key={i}><button className="link" onClick={() => onGo(s.tab)}>{s.text}</button></li>)}
        </ul>
      )}
      {r.parts.map((p) => (
        <details key={p.kind} className="part" open={r.parts.length === 1}>
          <summary>
            <b>{p.name}</b>{p.kind === r.main && r.parts.length > 1 && <span className="tag">like the real exam</span>}
            <span className="muted"> · estimate {p.estimate}% · practice {p.practice}% · mock exams {p.mock === null ? '—' : `${p.mock}%`} ({p.mocks}) · tried {p.coverage}%</span>
          </summary>
          <table>
            <thead><tr><th>Domain</th><th>Weight</th><th>Tried</th><th>Strength</th></tr></thead>
            <tbody>
              {p.domains.map((d) => (
                <tr key={d.id}>
                  <td>{d.name}</td><td>{d.weight}%</td><td>{d.seen}/{d.total}</td>
                  <td><span className="bar"><i style={{ width: `${d.strength}%` }} /></span> {d.strength}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      ))}
      <p className="facts-note">ℹ️ How it works: the estimate mixes your last 3 mock exams (60%) with your practice
        (40%), following the domain weights. In practice, a question you answered right several times in a row counts
        more than a new one; a lab solved within its target time counts more than a slow one. It is a guide, not a promise.</p>
    </>
  )
}

function Roadmap({ phases }) {
  return (
    <>
      <h2>Road to the exam</h2>
      <ol className="roadmap">
        {phases.map((p) => (
          <li key={p.phase} className={p.current ? 'current' : ''}>
            <b>{PHASE[p.phase]}</b> <span className="muted small">{fmtDate(p.start)}{p.end !== p.start ? ` – ${fmtDate(p.end)}` : ''}</span>
            <p className="small">{p.goal}</p>
          </li>
        ))}
      </ol>
    </>
  )
}
