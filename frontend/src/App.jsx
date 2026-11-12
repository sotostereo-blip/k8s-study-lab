import { useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import Labs from './Labs.jsx'

const TABS = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'practice', label: 'Practice' },
  { id: 'exam', label: 'Exam mode' },
  { id: 'labs', label: 'Labs (CKA)' },
  { id: 'glossary', label: 'Glossary' },
]

export default function App() {
  const [tab, setTab] = useState('dashboard')
  const [glossary, setGlossary] = useState([])
  const [exam, setExam] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.glossary(), api.exams()])
      .then(([g, e]) => { setGlossary(g); setExam(e.find((x) => x.id === 'kcna') || e[0]) })
      .catch((e) => setError(e.message))
  }, [])

  return (
    <div className="app">
      <header>
        <div className="brand"><span className="prompt">$</span> k8s-study-lab <span className="tag">{tab === 'labs' ? 'CKA' : 'KCNA'}</span></div>
        <nav>
          {TABS.map((t) => (
            <button key={t.id} className={tab === t.id ? 'active' : ''} onClick={() => setTab(t.id)}>{t.label}</button>
          ))}
        </nav>
      </header>
      <main className={tab === 'labs' ? 'wide' : ''}>
        {error && <p className="error">Cannot reach the API: {error}. Is the backend running on port 8000?</p>}
        {exam && tab === 'dashboard' && <Dashboard exam={exam} onGo={setTab} />}
        {exam && tab === 'practice' && <Practice exam={exam} glossary={glossary} />}
        {exam && tab === 'exam' && <ExamMode exam={exam} glossary={glossary} />}
        {tab === 'glossary' && <GlossaryPage glossary={glossary} />}
        {tab === 'labs' && <Labs />}
      </main>
    </div>
  )
}

/* ---------- Glossary-aware text: technical terms are clickable ---------- */

function GlossaryText({ text, termIds = [], glossary, onTranslate }) {
  const [open, setOpen] = useState(null)
  useEffect(() => {
    if (open === null) return
    const close = (e) => { if (!e.target.closest('.term-wrap')) setOpen(null) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])
  const toggleTerm = (p) => {
    const next = open === p.key ? null : p.key
    setOpen(next)
    if (next !== null) api.englishEvent('glossary_lookup', p.term.id).catch(() => {})
  }
  const terms = useMemo(() => glossary.filter((t) => termIds.includes(t.id)), [glossary, termIds])
  const parts = useMemo(() => {
    const forms = terms.flatMap((t) => t.match.map((m) => ({ m, t }))).sort((a, b) => b.m.length - a.m.length)
    if (!forms.length) return [text]
    const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const re = new RegExp(`\\b(${forms.map((f) => esc(f.m)).join('|')})\\b`, 'gi')
    const out = []
    let last = 0
    for (const match of text.matchAll(re)) {
      const term = forms.find((f) => f.m.toLowerCase() === match[0].toLowerCase()).t
      out.push(text.slice(last, match.index), { word: match[0], term, key: match.index })
      last = match.index + match[0].length
    }
    out.push(text.slice(last))
    return out
  }, [text, terms])

  return (
    <span>
      {parts.map((p, i) =>
        typeof p === 'string' ? p : (
          <span key={p.key} className="term-wrap">
            {/* span, not button: terms can appear inside option buttons */}
            <span className="term" role="button" tabIndex={0}
              onClick={(e) => { e.stopPropagation(); toggleTerm(p) }}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); toggleTerm(p) } }}
            >{p.word}</span>
            {open === p.key && <TermPopover term={p.term} onTranslate={onTranslate} onClose={() => setOpen(null)} />}
          </span>
        ),
      )}
    </span>
  )
}

function TermPopover({ term, onTranslate, onClose }) {
  const [showEs, setShowEs] = useState(false)
  return (
    <span className="popover" role="dialog">
      <strong>{term.term}</strong>
      <span>{term.definition}</span>
      {showEs ? <em className="es">ES: {term.es}</em> : (
        <button className="link" onClick={() => {
          setShowEs(true)
          onTranslate?.()
          api.englishEvent('translation', term.id).catch(() => {})
        }}>Show in Spanish</button>
      )}
      <button className="link close" onClick={onClose}>close</button>
    </span>
  )
}

/* ---------- Question card ---------- */

function QuestionCard({ q, glossary, selected, onChange, result, onTranslate, number }) {
  const toggle = (id) => {
    if (result) return
    if (q.type === 'single') onChange([id])
    else onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])
  }
  return (
    <div className="card">
      <div className="meta">
        {number && <span>Question {number}</span>}
        <span>{q.domain.replaceAll('-', ' ')}</span>
        <span>{'●'.repeat(q.difficulty)}{'○'.repeat(3 - q.difficulty)}</span>
      </div>
      <p className="question"><GlossaryText text={q.question} termIds={q.glossary} glossary={glossary} onTranslate={onTranslate} /></p>
      {q.type === 'multiple' && <p className="hint">Select {q.select} answers.</p>}
      <ul className="options">
        {q.options.map((o) => {
          const isSel = selected.includes(o.id)
          const isAns = result?.answer.includes(o.id)
          const cls = [isSel && 'selected', result && isAns && 'right', result && isSel && !isAns && 'wrong'].filter(Boolean).join(' ')
          return (
            <li key={o.id}>
              <button className={cls} onClick={() => toggle(o.id)} disabled={!!result}>
                <span className="key">{o.id.toUpperCase()}</span>
                <span className="opt-body">
                  <GlossaryText text={o.text} termIds={q.glossary} glossary={glossary} onTranslate={onTranslate} />
                  {result && !isAns && !isSel && result.why?.[o.id] && <span className="why">{result.why[o.id]}</span>}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
      {result && (
        <div className={`feedback ${result.correct ? 'ok' : 'ko'}`}>
          <strong>{result.correct ? 'Correct.' : 'Not quite.'}</strong>
          {!result.correct && <WrongReasons q={q} result={result} />}
          <p>{!result.correct && <b>Right answer: </b>}{result.explanation}</p>
          <p className="docs">Read more: {result.docs.map((d) => <a key={d} href={d} target="_blank" rel="noreferrer">{d.replace(/^https?:\/\//, '')}</a>)}</p>
        </div>
      )}
    </div>
  )
}

function WrongReasons({ q, result }) {
  const text = Object.fromEntries(q.options.map((o) => [o.id, o.text]))
  const chosenWrong = result.selected.filter((id) => !result.answer.includes(id))
  const missed = result.answer.filter((id) => !result.selected.includes(id))
  return (
    <div className="wrong-reasons">
      {chosenWrong.map((id) => (
        <p key={id}>
          <b>You chose {id.toUpperCase()} — “{text[id]}”.</b>{' '}
          {result.why?.[id] || 'This option does not answer the question.'}
        </p>
      ))}
      {missed.length > 0 && q.type === 'multiple' && (
        <p><b>You missed:</b> {missed.map((id) => `${id.toUpperCase()} — “${text[id]}”`).join('; ')}</p>
      )}
    </div>
  )
}

/* ---------- Dashboard ---------- */

function Dashboard({ exam, onGo }) {
  const [stats, setStats] = useState(null)
  useEffect(() => { api.stats(exam.id).then(setStats) }, [exam.id])
  if (!stats) return <p>Loading…</p>
  const e = stats.english
  const trRate = e.answers_total ? Math.round((100 * e.answers_with_translation) / e.answers_total) : 0
  const due = stats.domains.reduce((s, d) => s + d.due, 0)
  return (
    <section>
      <h1>{exam.name}</h1>
      <p className="sub">{exam.exam_questions} questions · {exam.exam_minutes} minutes · pass with {exam.passing_score}%</p>
      <div className="tiles">
        <div className="tile"><b>{due}</b><span>questions due for review</span></div>
        <div className="tile"><b>{stats.exams[0]?.score ?? '—'}{stats.exams[0] ? '%' : ''}</b><span>last mock exam</span></div>
        <div className="tile"><b>{trRate}%</b><span>answers that needed Spanish (goal: 0)</span></div>
      </div>
      <table>
        <thead><tr><th>Domain</th><th>Weight</th><th>Bank</th><th>Accuracy</th><th>Mastered</th></tr></thead>
        <tbody>
          {stats.domains.map((d) => (
            <tr key={d.id}>
              <td>{d.name}</td><td>{d.weight}%</td><td>{d.questions}</td>
              <td>{d.accuracy === null ? '—' : `${d.accuracy}%`}</td>
              <td>{d.mastered}/{d.questions}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="actions">
        <button className="primary" onClick={() => onGo('practice')}>Start practice</button>
        <button onClick={() => onGo('exam')}>Take a mock exam</button>
      </div>
    </section>
  )
}

/* ---------- Practice (spaced repetition) ---------- */

function Practice({ exam, glossary }) {
  const [domain, setDomain] = useState('')
  const [batch, setBatch] = useState(null)
  const [i, setI] = useState(0)
  const [selected, setSelected] = useState([])
  const [result, setResult] = useState(null)
  const [translated, setTranslated] = useState(false)
  const [score, setScore] = useState({ ok: 0, total: 0 })

  const load = () => {
    api.practiceNext(exam.id, domain || undefined, 10).then((b) => {
      setBatch(b); setI(0); setSelected([]); setResult(null); setTranslated(false); setScore({ ok: 0, total: 0 })
    })
  }
  useEffect(load, [domain])

  if (!batch) return <p>Loading…</p>
  const q = batch.questions[i]

  const check = async () => {
    const r = await api.answer({ question_id: q.id, selected, used_translation: translated })
    setResult(r)
    setScore((s) => ({ ok: s.ok + (r.correct ? 1 : 0), total: s.total + 1 }))
  }
  const next = () => { setI(i + 1); setSelected([]); setResult(null); setTranslated(false) }

  return (
    <section>
      <div className="toolbar">
        <select value={domain} onChange={(e) => setDomain(e.target.value)}>
          <option value="">All domains</option>
          {exam.domains.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <span className="sub">{batch.due} due · {batch.unseen} new · session {score.ok}/{score.total}</span>
      </div>
      {!q ? (
        <div className="card done">
          <h2>Session complete</h2>
          <p>You got {score.ok} of {score.total} right. Questions you missed will come back later today.</p>
          <button className="primary" onClick={load}>Load more</button>
        </div>
      ) : (
        <>
          <QuestionCard q={q} glossary={glossary} selected={selected} onChange={setSelected}
            result={result} onTranslate={() => setTranslated(true)} number={`${i + 1}/${batch.questions.length}`} />
          <div className="actions">
            {!result
              ? <button className="primary" disabled={!selected.length} onClick={check}>Check answer</button>
              : <button className="primary" onClick={next}>Next</button>}
          </div>
        </>
      )}
    </section>
  )
}

/* ---------- Exam mode ---------- */

function ExamMode({ exam, glossary }) {
  const [session, setSession] = useState(null)
  const [answers, setAnswers] = useState({})
  const [i, setI] = useState(0)
  const [left, setLeft] = useState(0)
  const [result, setResult] = useState(null)
  const [count, setCount] = useState(20)

  useEffect(() => {
    if (!session || result) return
    const end = Date.now() + session.minutes * 60000
    const t = setInterval(() => setLeft(Math.max(0, Math.round((end - Date.now()) / 1000))), 1000)
    setLeft(session.minutes * 60)
    return () => clearInterval(t)
  }, [session, result])

  const start = async () => {
    const s = await api.examStart({ exam_id: exam.id, questions: count })
    setSession(s); setAnswers({}); setI(0); setResult(null)
  }
  const submit = async () => setResult(await api.examSubmit(session.session_id, answers))

  if (result) return <ExamResult result={result} exam={exam} onAgain={() => { setSession(null); setResult(null) }} />

  if (!session) return (
    <section>
      <h1>Mock exam</h1>
      <p className="sub">Questions follow the official domain weights. The real exam has {exam.exam_questions} questions in {exam.exam_minutes} minutes; time scales with the number you choose.</p>
      <div className="toolbar">
        <label>Questions <input type="number" min="5" max={exam.exam_questions} value={count} onChange={(e) => setCount(+e.target.value)} /></label>
        <button className="primary" onClick={start}>Start exam</button>
      </div>
    </section>
  )

  const q = session.questions[i]
  const mm = String(Math.floor(left / 60)).padStart(2, '0')
  const ss = String(left % 60).padStart(2, '0')
  return (
    <section>
      <div className="toolbar">
        <span className={`timer ${left < 60 ? 'low' : ''}`}>{mm}:{ss}</span>
        <div className="dots">
          {session.questions.map((x, k) => (
            <button key={x.id} className={[k === i && 'cur', answers[x.id]?.length && 'done'].filter(Boolean).join(' ')} onClick={() => setI(k)}>{k + 1}</button>
          ))}
        </div>
      </div>
      <QuestionCard q={q} glossary={glossary} selected={answers[q.id] || []} number={`${i + 1}/${session.questions.length}`}
        onChange={(sel) => setAnswers({ ...answers, [q.id]: sel })} />
      <div className="actions">
        <button disabled={i === 0} onClick={() => setI(i - 1)}>Previous</button>
        {i < session.questions.length - 1
          ? <button className="primary" onClick={() => setI(i + 1)}>Next</button>
          : <button className="primary" onClick={submit}>Submit exam</button>}
        {left === 0 && <button className="primary" onClick={submit}>Time is up — submit</button>}
      </div>
    </section>
  )
}

function ExamResult({ result, exam, onAgain }) {
  const names = Object.fromEntries(exam.domains.map((d) => [d.id, d.name]))
  return (
    <section>
      <h1>{result.score}% — {result.passed ? 'Pass' : 'Not yet'}</h1>
      <p className="sub">{result.correct}/{result.total} correct · passing score {result.passing_score}% · {result.elapsed_minutes} min{result.overtime ? ' (over time)' : ''}</p>
      <table>
        <thead><tr><th>Domain</th><th>Result</th><th></th></tr></thead>
        <tbody>
          {Object.entries(result.domains).map(([id, d]) => {
            const pct = Math.round((100 * d.correct) / d.total)
            return <tr key={id}><td>{names[id]}</td><td>{d.correct}/{d.total}</td><td><div className="bar"><i style={{ width: `${pct}%` }} /></div></td></tr>
          })}
        </tbody>
      </table>
      <h2>Review</h2>
      {result.review.map((r, k) => (
        <details key={r.question_id} className={`review ${r.correct ? 'ok' : 'ko'}`}>
          <summary>{k + 1}. {r.correct ? '✓' : '✗'} {r.question}</summary>
          <ul>{r.options.map((o) => (
            <li key={o.id} className={r.answer.includes(o.id) ? 'right' : r.selected.includes(o.id) ? 'wrong' : ''}>
              {o.id.toUpperCase()}. {o.text}
              {!r.answer.includes(o.id) && o.why && <span className="why">{o.why}</span>}
            </li>
          ))}</ul>
          <p>{r.explanation}</p>
        </details>
      ))}
      <div className="actions"><button className="primary" onClick={onAgain}>New exam</button></div>
    </section>
  )
}

/* ---------- Glossary page ---------- */

function GlossaryPage({ glossary }) {
  const [q, setQ] = useState('')
  const [shown, setShown] = useState({})
  const list = glossary.filter((t) => (t.term + t.definition).toLowerCase().includes(q.toLowerCase()))
  return (
    <section>
      <h1>Glossary</h1>
      <p className="sub">Read the English definition first. Reveal the Spanish only if you need it.</p>
      <input className="search" placeholder="Search terms…" value={q} onChange={(e) => setQ(e.target.value)} />
      <dl className="glossary">
        {list.map((t) => (
          <div key={t.id}>
            <dt>{t.term}</dt>
            <dd>{t.definition}</dd>
            <dd>{shown[t.id] ? <em className="es">{t.es}</em> : (
              <button className="link" onClick={() => { setShown({ ...shown, [t.id]: true }); api.englishEvent('translation', t.id).catch(() => {}) }}>Show in Spanish</button>
            )}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
