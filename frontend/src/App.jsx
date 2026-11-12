import { useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import Labs from './Labs.jsx'
import { EnglishBar, EnglishContext, EnglishPage, EnglishText, ListenButton } from './english.jsx'

function tabsFor(cert) {
  return [
    ...(cert?.exam ? [
      { id: 'dashboard', label: 'Dashboard' },
      { id: 'practice', label: 'Practice' },
      { id: 'exam', label: 'Exam mode' },
    ] : []),
    ...(cert?.track ? [{ id: 'labs', label: 'Labs' }] : []),
    { id: 'english', label: 'English' },
    { id: 'glossary', label: 'Glossary' },
  ]
}

const loadCert = () => { try { return localStorage.getItem('cert') } catch { return null } }
const saveCert = (id) => { try { localStorage.setItem('cert', id) } catch { /* private mode */ } }

export default function App() {
  const [certs, setCerts] = useState([])
  const [certId, setCertId] = useState(loadCert)
  const [tab, setTab] = useState(null)
  const [glossary, setGlossary] = useState([])
  const [vocabulary, setVocabulary] = useState([])
  const [exams, setExams] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.glossary(), api.exams(), api.vocabulary(), api.certifications()])
      .then(([g, e, v, c]) => { setGlossary(g); setExams(e); setVocabulary(v); setCerts(c) })
      .catch((e) => setError(e.message))
  }, [])

  const cert = certs.find((c) => c.id === certId) || certs[0]
  const exam = exams.find((e) => e.id === cert?.exam)
  const tabs = tabsFor(cert)
  const current = tabs.some((t) => t.id === tab) ? tab : tabs[0].id
  const chooseCert = (id) => {
    setCertId(id); saveCert(id)
    const c = certs.find((x) => x.id === id)
    setTab(c?.exam ? 'dashboard' : 'labs')
  }
  const areas = [...new Set(certs.map((c) => c.area))]

  const english = useMemo(() => ({ glossary, vocabulary }), [glossary, vocabulary])
  return (
    <EnglishContext.Provider value={english}>
    <div className="app">
      <header>
        <div className="brand">
          <span className="prompt">$</span> k8s-study-lab
          {certs.length > 0 && (
            <select className="cert-select" value={cert?.id} onChange={(e) => chooseCert(e.target.value)} aria-label="Certification">
              {areas.map((a) => (
                <optgroup key={a} label={a}>
                  {certs.filter((c) => c.area === a).map((c) => <option key={c.id} value={c.id}>{c.short} — {c.name}</option>)}
                </optgroup>
              ))}
            </select>
          )}
        </div>
        <nav>
          {tabs.map((t) => (
            <button key={t.id} className={current === t.id ? 'active' : ''} onClick={() => setTab(t.id)}>{t.label}</button>
          ))}
        </nav>
      </header>
      <main className={current === 'labs' ? 'wide' : ''}>
        {error && <p className="error">Cannot reach the API: {error}. Is the backend running on port 8000?</p>}
        {exam && current === 'dashboard' && <Dashboard key={exam.id} exam={exam} cert={cert} onGo={setTab} />}
        {exam && current === 'practice' && <Practice key={exam.id} exam={exam} glossary={glossary} />}
        {exam && current === 'exam' && <ExamMode key={exam.id} exam={exam} glossary={glossary} />}
        {current === 'glossary' && <GlossaryPage glossary={glossary} vocabulary={vocabulary} />}
        {cert?.track && current === 'labs' && <Labs key={cert.track} trackId={cert.track} />}
        {current === 'english' && <EnglishPage />}
      </main>
    </div>
    </EnglishContext.Provider>
  )
}

/* ---------- Glossary-aware text (see english.jsx) ---------- */

function GlossaryText({ text, termIds, onTranslate }) {
  // `inline code` (commands, HCL, YAML) is shown as code and never highlighted as English
  const parts = (text || '').split(/(`[^`]+`)/g)
  return <span>{parts.map((p, i) => (p.startsWith('`') && p.endsWith('`') && p.length > 1
    ? <code key={i}>{p.slice(1, -1)}</code>
    : <EnglishText key={i} text={p} termIds={termIds} onTranslate={onTranslate} />))}</span>
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
      <EnglishBar text={[q.question, ...q.options.map((o) => o.text)].join('\n')} termIds={q.glossary} onTranslate={onTranslate}
        speakText={`${q.question} ${q.options.map((o) => `Option ${o.id.toUpperCase()}: ${o.text}.`).join(' ')}`} />
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
                  {result && !isAns && !isSel && result.why?.[o.id] && <span className="why"><GlossaryText text={result.why[o.id]} termIds={q.glossary} onTranslate={onTranslate} /></span>}
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
          <p>{!result.correct && <b>Right answer: </b>}<GlossaryText text={result.explanation} termIds={q.glossary} onTranslate={onTranslate} /></p>
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
          <GlossaryText text={result.why?.[id] || 'This option does not answer the question.'} termIds={q.glossary} />
        </p>
      ))}
      {missed.length > 0 && q.type === 'multiple' && (
        <p><b>You missed:</b> {missed.map((id) => `${id.toUpperCase()} — “${text[id]}”`).join('; ')}</p>
      )}
    </div>
  )
}

/* ---------- Dashboard ---------- */

function Dashboard({ exam, cert, onGo }) {
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
      {exam.facts_note && <p className="facts-note">ℹ️ {exam.facts_note}</p>}
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
        {cert?.track && <button onClick={() => onGo('labs')}>Hands-on labs</button>}
        <button onClick={() => onGo('english')}>Practise exam English</button>
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

function GlossaryPage({ glossary, vocabulary }) {
  const [q, setQ] = useState('')
  const [kind, setKind] = useState('term')
  const [shown, setShown] = useState({})
  const all = kind === 'term'
    ? glossary.map((t) => ({ ...t, name: t.term, ref: t.id }))
    : vocabulary.map((w) => ({ ...w, name: w.word, ref: `word:${w.id}` }))
  const list = all.filter((t) => (t.name + t.definition).toLowerCase().includes(q.toLowerCase()))
  return (
    <section>
      <h1>Glossary</h1>
      <p className="sub">Read the English definition first. Listen to it. Reveal the Spanish only if you need it.</p>
      <div className="chips">
        <button className={kind === 'term' ? 'active' : ''} onClick={() => setKind('term')}>Technical terms ({glossary.length})</button>
        <button className={kind === 'word' ? 'active' : ''} onClick={() => setKind('word')}>Exam English ({vocabulary.length})</button>
      </div>
      <input className="search" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} />
      <dl className="glossary">
        {list.map((t) => (
          <div key={t.ref}>
            <dt>{t.name} <ListenButton text={t.name} refId={t.ref} label="" /></dt>
            <dd>{t.definition}</dd>
            {t.example && <dd className="example">“{t.example}”</dd>}
            <dd>{shown[t.ref] ? <em className="es">{t.es}</em> : (
              <button className="link" onClick={() => { setShown({ ...shown, [t.ref]: true }); api.englishEvent('translation', t.ref).catch(() => {}) }}>Show in Spanish</button>
            )}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
