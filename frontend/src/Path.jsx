import { useState } from 'react'
import { api } from './api.js'

const COLUMNS = ['Start here', 'Next', 'Then']
const STATUS = {
  active: { label: 'Passed', cls: 'ok' },
  expiring: { label: 'Expires soon', cls: 'warn' },
  expired: { label: 'Expired', cls: 'ko' },
  goal: { label: 'Exam booked', cls: 'accent' },
  none: { label: 'Not passed yet', cls: 'muted' },
}
const fmtDate = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
const isoToday = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10) }

/* Expiry and prerequisite reminders, shown on every page. */
export function Reminders({ path, onOpen }) {
  if (!path?.reminders?.length) return null
  return (
    <div className="reminders">
      {path.reminders.map((r, i) => (
        <p key={i} className={`reminder ${r.level}`}>
          <span>{r.level === 'ko' ? '⛔' : '⏰'} {r.text}</span>
          {onOpen && <button className="link" onClick={onOpen}>My path</button>}
        </p>
      ))}
    </div>
  )
}

export default function PathMap({ path, onChange, onStudy }) {
  if (!path) return <p>Loading…</p>
  const short = Object.fromEntries(path.certs.map((c) => [c.id, c.short]))
  const levels = [...new Set(path.certs.map((c) => c.level))].sort()
  return (
    <section className="path">
      <h1>My certification path</h1>
      <p className="sub">A suggested order, the exams that need another certification first, and when the ones you passed
        expire. Record a certification when you pass it: the app reminds you {path.expiring_days} days before it expires.</p>
      <Reminders path={path} />
      {path.programs.map((p) => (
        <div key={p.id} className="program card">
          <div>
            <b>{p.name}</b> <span className="muted small">{p.active.length}/{p.certs.length}{p.complete && p.until ? ` · complete until ${fmtDate(p.until)}` : ''}</span>
            <p className="small">{p.description} <a href={p.url} target="_blank" rel="noreferrer">Official page</a></p>
          </div>
          <div className="chips">
            {p.certs.map((c) => <span key={c} className={`chip ${p.active.includes(c) ? 'ok' : ''}`}>{p.active.includes(c) ? '✓ ' : ''}{short[c]}</span>)}
          </div>
        </div>
      ))}
      <div className="path-columns">
        {levels.map((l) => (
          <div key={l} className="path-column">
            <h2>{COLUMNS[l] || `Step ${l + 1}`}</h2>
            {path.certs.filter((c) => c.level === l).map((c) => (
              <CertCard key={c.id} c={c} short={short} onChange={onChange} onStudy={onStudy} />
            ))}
          </div>
        ))}
      </div>
      <p className="facts-note">ℹ️ “After” is a suggestion: those exams share topics, so the first one makes the next one
        easier. “Requires” is a rule of the real exam. Expiry dates follow the official validity; if your certificate shows
        another date, enter it.</p>
    </section>
  )
}

function CertCard({ c, short, onChange, onStudy }) {
  const [editing, setEditing] = useState(false)
  const [passed, setPassed] = useState(c.passed_on || '')
  const [expires, setExpires] = useState('')
  const [error, setError] = useState(null)
  const st = STATUS[c.status]
  const save = (e) => {
    e.preventDefault()
    api.earnedSet(c.id, { passed_on: passed, expires_on: expires || null })
      .then((p) => { setEditing(false); setError(null); onChange(p) }).catch((err) => setError(err.message))
  }
  const r = c.readiness
  return (
    <div className={`path-card card status-${c.status}`}>
      <div className="path-card-head">
        <b>{c.short}</b>
        <span className={`verdict ${st.cls}`}>{st.label}</span>
      </div>
      <p className="small muted">{c.name}</p>
      {c.requires.map((x) => (
        <p key={x} className={`small ${c.missing_requires.includes(x) ? 'ko-text' : ''}`}>
          Requires {short[x]}{c.missing_requires.includes(x) ? ' (not recorded yet)' : ' ✓'}
        </p>
      ))}
      {c.after.filter((x) => !c.requires.includes(x)).length > 0 && (
        <p className="small muted">Study after {c.after.filter((x) => !c.requires.includes(x)).map((x) => short[x]).join(', ')}</p>
      )}
      {c.passed_on && (
        <p className="small">Passed {fmtDate(c.passed_on)}{c.expires_on && <> · {c.days_left < 0 ? 'expired' : 'expires'} {fmtDate(c.expires_on)}</>}
          {c.extended_by && <span className="muted"> (extended by your {c.extended_by})</span>}</p>
      )}
      {c.exam_date && !c.passed_on && <p className="small">Exam on {fmtDate(c.exam_date)}</p>}
      {r && (
        <p className="small muted">Estimate {r.verdict === 'unknown' ? `${r.estimate}% (no mock exam yet)` : `${r.estimate}%`} · need {r.passing}%</p>
      )}
      {(c.status === 'expiring' || c.status === 'expired') && <p className="small">{c.renewal}</p>}
      {editing ? (
        <form className="earned-form" onSubmit={save}>
          <label>Passed on <input type="date" required max={isoToday()} value={passed} onChange={(e) => setPassed(e.target.value)} /></label>
          <label>Expires on <span className="muted">(optional)</span> <input type="date" value={expires} min={passed} onChange={(e) => setExpires(e.target.value)} /></label>
          <div className="actions">
            <button className="primary" type="submit" disabled={!passed}>Save</button>
            <button type="button" onClick={() => setEditing(false)}>Cancel</button>
          </div>
          {error && <p className="error small">{error}</p>}
        </form>
      ) : (
        <div className="actions">
          <button onClick={() => onStudy(c.id)}>{c.passed_on ? 'Practise' : 'Study'}</button>
          <button className="link" onClick={() => setEditing(true)}>{c.passed_on ? 'Edit' : 'I passed it'}</button>
          {c.passed_on && <button className="link" onClick={() => api.earnedDelete(c.id).then(onChange)}>Remove</button>}
        </div>
      )}
    </div>
  )
}
