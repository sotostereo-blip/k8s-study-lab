import { useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import { ExplainMore, useAiEnabled } from './AiHelp.jsx'
import Labs from './Labs.jsx'
import Plan from './Plan.jsx'
import PathMap, { Reminders } from './Path.jsx'
import { InterviewPractice, MockInterview, Phrases } from './Interview.jsx'
import { EnglishBar, EnglishContext, EnglishPage, EnglishText, ListenButton } from './english.jsx'

function tabsFor(cert) {
  return [
    ...(cert ? [{ id: 'plan', label: 'Plan' }] : []),
    ...(cert?.exam ? [
      { id: 'dashboard', label: 'Dashboard' },
      { id: 'practice', label: 'Practice' },
      { id: 'exam', label: 'Exam mode' },
    ] : []),
    ...(cert?.track ? [{ id: 'labs', label: 'Labs' }] : []),
    ...(cert?.interview ? [
      { id: 'interview', label: 'Practice' },
      { id: 'mock-interview', label: 'Mock interview' },
      { id: 'phrases', label: 'Phrases' },
    ] : []),
    ...(cert?.official ? [{ id: 'real-exam', label: 'Real exam' }] : []),
    { id: 'path', label: 'My path' },
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
  const [practiceDomain, setPracticeDomain] = useState('')
  const [glossary, setGlossary] = useState([])
  const [vocabulary, setVocabulary] = useState([])
  const [exams, setExams] = useState([])
  const [error, setError] = useState(null)
  const [path, setPath] = useState(null)
  const loadPath = () => api.path().then(setPath).catch(() => {})

  useEffect(() => {
    Promise.all([api.glossary(), api.exams(), api.vocabulary(), api.certifications()])
      .then(([g, e, v, c]) => { setGlossary(g); setExams(e); setVocabulary(v); setCerts(c) })
      .catch((e) => setError(e.message))
    loadPath()
  }, [])
  useEffect(() => { if (tab === 'path' || tab === 'plan') loadPath() }, [tab, certId])

  const cert = certs.find((c) => c.id === certId) || certs[0]
  const exam = exams.find((e) => e.id === cert?.exam)
  const tabs = tabsFor(cert)
  const current = tabs.some((t) => t.id === tab) ? tab : tabs[0].id
  const chooseCert = (id) => {
    setCertId(id); saveCert(id)
    const c = certs.find((x) => x.id === id)
    setTab(c ? 'plan' : null)
  }
  const go = (t, opts) => { if (opts?.domain !== undefined) setPracticeDomain(opts.domain); setTab(t) }
  const areas = [...new Set(certs.map((c) => c.area))]

  const english = useMemo(() => ({ glossary, vocabulary, cert: cert?.id }), [glossary, vocabulary, cert?.id])
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
            <button key={t.id} className={current === t.id ? 'active' : ''} onClick={() => { if (t.id === 'practice') setPracticeDomain(''); setTab(t.id) }}>{t.label}</button>
          ))}
        </nav>
      </header>
      <main className={current === 'labs' ? 'wide' : ''}>
        {error && <p className="error">Cannot reach the API: {error}. Is the backend running on port 8000?</p>}
        {current !== 'path' && <Reminders path={path} onOpen={() => setTab('path')} />}
        {current === 'path' && <PathMap path={path} onChange={setPath} onStudy={chooseCert} />}
        {cert && current === 'plan' && <Plan key={cert.id} cert={cert} onGo={go} />}
        {exam && current === 'dashboard' && <Dashboard key={exam.id} exam={exam} cert={cert} onGo={go} />}
        {exam && current === 'practice' && <Practice key={`${exam.id}-${practiceDomain}`} exam={exam} glossary={glossary} initialDomain={practiceDomain} />}
        {exam && current === 'exam' && <ExamMode key={exam.id} exam={exam} glossary={glossary} onGo={go} />}
        {current === 'glossary' && <GlossaryPage glossary={glossary} vocabulary={vocabulary} />}
        {cert?.track && current === 'labs' && <Labs key={cert.track} trackId={cert.track} />}
        {current === 'english' && <EnglishPage />}
        {cert?.interview && current === 'interview' && <InterviewPractice />}
        {cert?.interview && current === 'mock-interview' && <MockInterview />}
        {cert?.interview && current === 'phrases' && <Phrases />}
        {cert?.official && current === 'real-exam' && <RealExam cert={cert} />}
      </main>
    </div>
    </EnglishContext.Provider>
  )
}

/* ---------- Glossary-aware text (see english.jsx) ---------- */

function GlossaryText({ text, termIds, onTranslate, plain }) {
  // `inline code` (commands, HCL, YAML) is shown as code and never highlighted as English
  const parts = (text || '').split(/(`[^`]+`)/g)
  return <span>{parts.map((p, i) => (p.startsWith('`') && p.endsWith('`') && p.length > 1
    ? <code key={i}>{p.slice(1, -1)}</code>
    : plain ? <span key={i}>{p}</span> : <EnglishText key={i} text={p} termIds={termIds} onTranslate={onTranslate} />))}</span>
}

/* ---------- Question card ---------- */

function QuestionCard({ q, glossary, selected, onChange, result, onTranslate, number, plain }) {
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
      <p className="question"><GlossaryText text={q.question} termIds={q.glossary} plain={plain} onTranslate={onTranslate} /></p>
      {!plain && <EnglishBar text={[q.question, ...q.options.map((o) => o.text)].join('\n')} termIds={q.glossary} onTranslate={onTranslate}
        speakText={`${q.question} ${q.options.map((o) => `Option ${o.id.toUpperCase()}: ${o.text}.`).join(' ')}`} />}
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
                  <GlossaryText text={o.text} termIds={q.glossary} plain={plain} onTranslate={onTranslate} />
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
      {cert?.official && (
        <p className="sub">Real exam: {cert.official.cost} · valid {cert.official.valid}{cert.facts_stale ? ' · ⚠️ facts may be out of date' : ''} ·{' '}
          <button className="link" onClick={() => onGo('real-exam')}>all the facts</button></p>
      )}
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

/* ---------- Real exam facts ---------- */

function RealExam({ cert }) {
  const o = cert.official
  const hours = o.minutes >= 60 ? ` (${+(o.minutes / 60).toFixed(1)} h)` : ''
  const rows = [
    ['Provider', o.provider],
    ['Format', o.format],
    ['Questions', o.questions],
    ['Time', `${o.minutes} minutes${hours}`],
    ['Passing score', o.passing || 'Not published'],
    ['Cost', o.cost],
    ['Prerequisites', o.prerequisites],
    ['Valid for', o.valid],
    ['Renewal', o.renewal],
  ].filter(([, v]) => v)
  return (
    <section className="real-exam">
      <h1>{cert.name}</h1>
      <p className="sub">The real exam, as described on the official page.</p>
      {cert.facts_stale && (
        <p className="reminder">⚠️ These facts were checked {cert.facts_age_months} months ago ({o.checked}) and may be out of
          date. Check the <a href={o.url} target="_blank" rel="noreferrer">official page</a> before you pay or book.</p>
      )}
      <div className="tiles">
        <div className="tile"><b>{o.minutes}</b><span>minutes</span></div>
        <div className="tile"><b>{/^USD [\d.]+/.exec(o.cost)?.[0] || 'Varies'}</b><span>exam price</span></div>
        <div className="tile"><b>{o.valid.split(' (')[0]}</b><span>certification is valid</span></div>
      </div>
      <table>
        <tbody>{rows.map(([k, v]) => <tr key={k}><th>{k}</th><td><EnglishText text={v} /></td></tr>)}</tbody>
      </table>
      {o.includes.length > 0 && (<><h2>What you get when you pay</h2><ul>{o.includes.map((x) => <li key={x}><EnglishText text={x} /></li>)}</ul></>)}
      {o.notes.length > 0 && (<><h2>Good to know</h2><ul>{o.notes.map((x) => <li key={x}><EnglishText text={x} /></li>)}</ul></>)}
      <p className="facts-note">ℹ️ Checked in {o.checked}. Prices, rules and question counts change: check the{' '}
        <a href={o.url} target="_blank" rel="noreferrer">official page</a> before you pay or book.</p>
    </section>
  )
}

/* ---------- Practice (spaced repetition) ---------- */

function Practice({ exam, glossary, initialDomain = '' }) {
  const ai = useAiEnabled()
  const [domain, setDomain] = useState(initialDomain)
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
          {result && ai && <ExplainMore key={q.id} q={q} selected={selected} />}
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

function ExamMode({ exam, glossary, onGo }) {
  const [session, setSession] = useState(null)
  const [answers, setAnswers] = useState({})
  const [domcAnswers, setDomcAnswers] = useState({})   // DOMC: { qid: { optionId: yes } }
  const [domcDone, setDomcDone] = useState({})
  const [flags, setFlags] = useState({})
  const [i, setI] = useState(0)
  const [left, setLeft] = useState(0)
  const [result, setResult] = useState(null)
  const [confirming, setConfirming] = useState(false)
  const [count, setCount] = useState(Math.min(20, exam.exam_questions))
  const [real, setReal] = useState(false)
  const [esl, setEsl] = useState(false)
  const [domc, setDomc] = useState(exam.domc > 0)

  useEffect(() => {
    if (!session || result) return
    const end = Date.now() + session.minutes * 60000
    const t = setInterval(() => setLeft(Math.max(0, Math.round((end - Date.now()) / 1000))), 1000)
    setLeft(session.minutes * 60)
    return () => clearInterval(t)
  }, [session, result])

  const start = async () => {
    const s = await api.examStart({ exam_id: exam.id, questions: count, real, esl, domc })
    setSession(s); setAnswers({}); setDomcAnswers({}); setDomcDone({}); setFlags({}); setI(0); setResult(null); setConfirming(false)
  }
  const submit = async () => setResult(await api.examSubmit(session.session_id, answers, domcAnswers))

  if (result) return <ExamResult result={result} exam={exam} flags={flags} onGo={onGo} onAgain={() => { setSession(null); setResult(null) }} />

  if (!session) {
    const scale = count / exam.exam_questions
    const minutes = Math.max(1, Math.round(exam.exam_minutes * scale)) + (esl && exam.esl_minutes ? Math.max(1, Math.round(exam.esl_minutes * scale)) : 0)
    return (
      <section>
        <h1>Mock exam</h1>
        <p className="sub">Questions follow the official domain weights. The real exam has {exam.exam_questions} questions in {exam.exam_minutes} minutes; time scales with the number you choose.</p>
        <div className="toolbar">
          <label>Questions <input type="number" min="5" max={exam.exam_questions} value={count} onChange={(e) => setCount(+e.target.value)} /></label>
          <button className="link" onClick={() => setCount(exam.exam_questions)}>Full length ({exam.exam_questions})</button>
          <span className="sub">{minutes} minutes</span>
        </div>
        <div className="exam-options">
          <label className="check-row">
            <input type="checkbox" checked={real} onChange={(e) => setReal(e.target.checked)} />
            <span><b>Real exam conditions.</b> No glossary, no Spanish translation and no listening: the real exam is only in
              English. Use it when you practise for the day of the exam.</span>
          </label>
          {exam.domc > 0 && (
            <label className="check-row">
              <input type="checkbox" checked={domc} onChange={(e) => setDomc(e.target.checked)} />
              <span><b>DOMC questions, like the real exam</b> ({exam.domc} of {exam.exam_questions}). The options appear one at a
                time and you answer YES or NO to each. You cannot go back to an option, and the question can end early.</span>
            </label>
          )}
          {exam.esl_minutes > 0 && (
            <label className="check-row">
              <input type="checkbox" checked={esl} onChange={(e) => setEsl(e.target.checked)} />
              <span><b>English is not my first language (+{exam.esl_minutes} minutes).</b> The real exam gives this extra time only
                if you request the ESL accommodation in your exam account <i>before</i> you book the exam.</span>
            </label>
          )}
        </div>
        <div className="actions"><button className="primary" onClick={start}>Start exam</button></div>
      </section>
    )
  }

  const q = session.questions[i]
  const isDomc = (x) => x.style === 'domc'
  const answered = (x) => (isDomc(x) ? domcDone[x.id] : answers[x.id]?.length > 0)
  const unanswered = session.questions.filter((x) => !answered(x)).length
  const flagged = session.questions.filter((x) => flags[x.id]).length
  const mm = String(Math.floor(left / 60)).padStart(2, '0')
  const ss = String(left % 60).padStart(2, '0')
  return (
    <section>
      <div className="toolbar">
        <span className={`timer ${left < 60 ? 'low' : ''}`}>{mm}:{ss}</span>
        <div className="dots">
          {session.questions.map((x, k) => (
            <button key={x.id} className={[k === i && 'cur', answered(x) && 'done', flags[x.id] && 'flag'].filter(Boolean).join(' ')} onClick={() => setI(k)}>{k + 1}</button>
          ))}
        </div>
      </div>
      {isDomc(q)
        ? <DomcCard key={q.id} q={q} sessionId={session.session_id} plain={session.conditions?.real}
            number={`${i + 1}/${session.questions.length}`} responses={domcAnswers[q.id] || {}} done={!!domcDone[q.id]}
            onAnswer={(r, done) => { setDomcAnswers((a) => ({ ...a, [q.id]: r })); if (done) setDomcDone((d) => ({ ...d, [q.id]: true })) }} />
        : <QuestionCard q={q} glossary={glossary} selected={answers[q.id] || []} number={`${i + 1}/${session.questions.length}`}
            plain={session.conditions?.real} onChange={(sel) => setAnswers({ ...answers, [q.id]: sel })} />}
      {confirming ? (
        <div className="confirm">
          <p>Submit the exam now?{unanswered ? ` ${unanswered} question${unanswered > 1 ? 's are' : ' is'} not answered (they count as wrong).` : ''}
            {flagged ? ` ${flagged} flagged for review.` : ''}</p>
          <div className="actions">
            <button className="primary" onClick={submit}>Yes, submit</button>
            <button onClick={() => setConfirming(false)}>Keep working</button>
          </div>
        </div>
      ) : (
        <div className="actions">
          <button disabled={i === 0} onClick={() => setI(i - 1)}>Previous</button>
          {i < session.questions.length - 1
            ? <button className="primary" onClick={() => setI(i + 1)}>Next</button>
            : <button className="primary" onClick={() => setConfirming(true)}>Submit exam</button>}
          <button onClick={() => setFlags({ ...flags, [q.id]: !flags[q.id] })}>{flags[q.id] ? '★ Flagged' : '☆ Flag for review'}</button>
          {i < session.questions.length - 1 && <button className="link" onClick={() => setConfirming(true)}>Submit now</button>}
          {left === 0 && <button className="primary" onClick={submit}>Time is up — submit</button>}
        </div>
      )}
    </section>
  )
}

/* DOMC: one option at a time, YES or NO; the server says when the question is over. */
function DomcCard({ q, sessionId, number, responses, done, onAnswer, plain }) {
  const [current, setCurrent] = useState(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (done) return
    api.examDomc(sessionId, q.id, responses).then((s) => setCurrent(s.next))
  }, [q.id])
  const answer = async (yes) => {
    setBusy(true)
    const r = { ...responses, [current.id]: yes }
    const s = await api.examDomc(sessionId, q.id, r)
    onAnswer(r, s.done)
    setCurrent(s.next); setBusy(false)
  }
  const seen = Object.keys(responses).length
  return (
    <div className="card domc">
      <div className="meta">
        <span>Question {number}</span>
        <span>DOMC</span>
        <span>{q.domain.replaceAll('-', ' ')}</span>
      </div>
      <p className="question"><GlossaryText text={q.question} termIds={q.glossary} plain={plain} /></p>
      {!plain && <EnglishBar text={q.question} termIds={q.glossary} speakText={q.question} />}
      <p className="hint">One option at a time. Is this option a right answer? More than one option can be right.</p>
      {done || !current ? (
        <p className="domc-done">✓ Answer recorded ({seen} option{seen === 1 ? '' : 's'} seen). You cannot change it.</p>
      ) : (
        <div className="domc-option">
          <span className="key">{seen + 1}</span>
          <span className="opt-body"><GlossaryText text={current.text} termIds={q.glossary} plain={plain} /></span>
          <div className="domc-buttons">
            <button className="primary" disabled={busy} onClick={() => answer(true)}>YES</button>
            <button disabled={busy} onClick={() => answer(false)}>NO</button>
          </div>
        </div>
      )}
    </div>
  )
}

function ExamResult({ result, exam, flags, onGo, onAgain }) {
  const domains = Object.fromEntries(exam.domains.map((d) => [d.id, d]))
  const rows = Object.entries(result.domains).map(([id, d]) => ({ id, ...d, pct: Math.round((100 * d.correct) / d.total) }))
    .sort((a, b) => (domains[b.id]?.weight || 0) - (domains[a.id]?.weight || 0))
  const weak = rows.filter((r) => r.pct < result.passing_score)
  const c = result.conditions || {}
  const tags = [c.real && 'real exam conditions', c.esl && `ESL +${exam.esl_minutes} min`,
    result.review.some((r) => r.style === 'domc') && 'DOMC'].filter(Boolean)
  return (
    <section>
      <h1>{result.score}% — {result.passed ? 'Pass' : 'Not yet'}</h1>
      <p className="sub">{result.correct}/{result.total} correct · passing score {result.passing_score}% · {result.elapsed_minutes} min{result.overtime ? ' (over time)' : ''}
        {tags.length > 0 && ` · ${tags.join(' · ')}`}</p>
      <h2>By domain</h2>
      <table>
        <thead><tr><th>Domain</th><th>Weight</th><th>Result</th><th></th></tr></thead>
        <tbody>
          {rows.map((d) => (
            <tr key={d.id} className={d.pct < result.passing_score ? 'weak' : ''}>
              <td>{domains[d.id]?.name}</td><td>{domains[d.id]?.weight}%</td><td>{d.correct}/{d.total} ({d.pct}%)</td>
              <td><div className="bar"><i style={{ width: `${d.pct}%` }} /><em style={{ left: `${result.passing_score}%` }} /></div></td>
            </tr>
          ))}
        </tbody>
      </table>
      {weak.length > 0 ? (
        <div className="weak-list">
          <p><b>Study next:</b> these domains are below the passing score. You pass with your total score, but a weak
            domain with a big weight pulls the total down.</p>
          <ul>{weak.map((d) => (
            <li key={d.id}><button className="link" onClick={() => onGo?.('practice', { domain: d.id })}>
              Practise “{domains[d.id]?.name}” ({d.pct}%, weight {domains[d.id]?.weight}%)</button></li>
          ))}</ul>
        </div>
      ) : <p className="pace pace-ahead">Every domain is at or above the passing score.</p>}
      <h2>Review</h2>
      {result.review.map((r, k) => (
        <details key={r.question_id} className={`review ${r.correct ? 'ok' : 'ko'}`} open={!r.correct && flags?.[r.question_id]}>
          <summary>{k + 1}. {r.correct ? '✓' : '✗'} {flags?.[r.question_id] ? '★ ' : ''}{r.question}</summary>
          {r.style === 'domc' && (
            <p className="small muted">DOMC — you saw: {r.domc.length ? r.domc.map((x) => `${x.id.toUpperCase()} ${x.yes ? 'YES' : 'NO'}`).join(', ') : 'no options (not answered)'}</p>
          )}
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
