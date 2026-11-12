import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { EnglishBar, EnglishText, ListenButton, speak } from './english.jsx'

/* Job interviews in English: hear the question, answer aloud (speech to text when the browser
   supports it, or type), then compare with the key points and a model answer. */

const Recognition = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition)
const FILLERS = ['um', 'uh', 'erm', 'like', 'you know', 'basically', 'actually', 'kind of', 'sort of']
const STOP = new Set('a an the and or but of to in on for with is are be by it this that as at from your you i we can how what why when which their there they them use used using have has will would should could do does'.split(' '))

const words = (t) => (t.trim() ? t.trim().split(/\s+/).length : 0)
const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
const label = { technical: 'technical', behavioral: 'behavioral (STAR)', scenario: 'scenario', design: 'system design' }

/** Key points whose main words appear in the answer: a suggestion, the learner decides. */
function suggest(points, answer) {
  const text = answer.toLowerCase()
  return points.flatMap((p, i) => {
    const keys = p.toLowerCase().match(/[a-z0-9][a-z0-9-]{2,}/g)?.filter((w) => !STOP.has(w)) || []
    if (!keys.length) return []
    const hit = keys.filter((k) => text.includes(k.length > 5 ? k.slice(0, -2) : k)).length
    return hit / keys.length >= 0.5 ? [i] : []
  })
}

function fillerCount(answer) {
  const t = ` ${answer.toLowerCase().replace(/[^a-z' ]/g, ' ')} `
  return FILLERS.map((f) => [f, t.split(` ${f} `).length - 1]).filter(([, n]) => n > 0)
}

/* ---------- speech to text ---------- */

function useDictation(onText) {
  const [on, setOn] = useState(false)
  const [blocked, setBlocked] = useState(false)
  const [used, setUsed] = useState(false)   // some words came from the microphone
  const rec = useRef(null)
  const stop = () => { rec.current?.stop(); setOn(false) }
  const start = () => {
    if (!Recognition) return
    const r = new Recognition()
    r.lang = 'en-US'
    r.continuous = true
    r.interimResults = false
    r.onresult = (e) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) { onText(e.results[i][0].transcript.trim()); setUsed(true) }
      }
    }
    r.onend = () => setOn(false)
    r.onerror = (e) => { setOn(false); if (e.error === 'not-allowed' || e.error === 'service-not-allowed') setBlocked(true) }
    r.start()
    rec.current = r
    setOn(true)
  }
  useEffect(() => () => rec.current?.abort(), [])
  return { supported: !!Recognition && !blocked, blocked, used, on, start, stop }
}

/* ---------- one question: answer, then self-check ---------- */

export function AnswerCard({ q, number, sessionId, onDone, doneLabel = 'Next question' }) {
  const [phase, setPhase] = useState('read')        // read | answer | review
  const [answer, setAnswer] = useState('')
  const [startAt, setStartAt] = useState(null)
  const [seconds, setSeconds] = useState(0)
  const [now, setNow] = useState(Date.now())
  const [review, setReview] = useState(null)
  const [covered, setCovered] = useState([])
  const [suggested, setSuggested] = useState([])
  const [saving, setSaving] = useState(false)
  const dict = useDictation((t) => setAnswer((a) => (a ? `${a} ${t}` : t)))

  useEffect(() => { if (phase === 'read') speak(q.question, 0.9) }, [q.id])
  useEffect(() => {
    if (phase !== 'answer') return
    const t = setInterval(() => setNow(Date.now()), 500)
    return () => clearInterval(t)
  }, [phase])

  const begin = () => { setPhase('answer'); setStartAt(Date.now()); setNow(Date.now()); if (dict.supported) dict.start() }
  const finish = async () => {
    dict.stop()
    setSeconds(Math.max(1, Math.round((Date.now() - startAt) / 1000)))
    const r = await api.interviewReview(q.id)
    const s = suggest(r.key_points, answer)
    setReview(r); setSuggested(s); setCovered(s); setPhase('review')
  }
  const save = async () => {
    setSaving(true)
    try {
      // speaking pace only counts answers spoken into the microphone (typing is much faster)
      const r = await api.interviewGrade({ question_id: q.id, covered, seconds, words: dict.used ? words(answer) : null, session_id: sessionId })
      onDone?.(r)
    } finally { setSaving(false) }
  }

  const elapsed = startAt ? Math.round((now - startAt) / 1000) : 0
  const target = Math.round(q.minutes * 60)
  const wpm = dict.used && seconds && words(answer) ? Math.round((60 * words(answer)) / seconds) : null
  const fillers = fillerCount(answer)

  return (
    <div className="card interview-card">
      <div className="meta">
        {number && <span>Question {number}</span>}
        <span>{q.category}</span>
        <span>{q.level}</span>
        <span>{label[q.type]}</span>
        <span>~{q.minutes} min</span>
      </div>
      <p className="question"><EnglishText text={q.question} termIds={q.glossary} /></p>
      <EnglishBar text={q.question} termIds={q.glossary} />

      {phase === 'read' && (
        <>
          {q.tips && <details className="tips"><summary>How to answer</summary><p><EnglishText text={q.tips} /></p></details>}
          <div className="actions">
            <button className="primary" onClick={begin}>{dict.supported ? '🎙 Start answering aloud' : 'Start answering'}</button>
          </div>
          {!dict.supported && <p className="sub">Your browser has no speech to text (Chrome has it). Say your answer aloud and type the main ideas, or just type it.</p>}
        </>
      )}

      {phase === 'answer' && (
        <>
          {dict.blocked && <p className="sub">The microphone is blocked in this browser. Say your answer aloud and type the main ideas.</p>}
          <p className={`timer ${elapsed > target ? 'low' : ''}`}>{fmt(elapsed)} <small>/ {fmt(target)} target</small></p>
          <textarea className="answer" rows={7} value={answer} onChange={(e) => setAnswer(e.target.value)}
            placeholder={dict.supported ? 'Speak — your words appear here. You can also type or correct them.' : 'Type your answer (or the main ideas you said aloud).'} />
          <div className="actions">
            {dict.supported && (dict.on
              ? <button onClick={dict.stop}>⏸ Pause microphone</button>
              : <button onClick={dict.start}>🎙 Resume microphone</button>)}
            {dict.on && <span className="rec">● listening</span>}
            <button className="primary" onClick={finish}>I'm done</button>
          </div>
        </>
      )}

      {phase === 'review' && review && (
        <div className="iv-review">
          <div className="iv-stats">
            <span>⏱ {fmt(seconds)} (target {fmt(target)})</span>
            <span>{words(answer)} words</span>
            {wpm && <span title="A clear interview pace is about 110-150 words per minute">{wpm} words/min</span>}
            {fillers.length > 0 && <span>filler words: {fillers.map(([f, n]) => `${f} ×${n}`).join(', ')}</span>}
          </div>
          <h3>Did your answer cover these points?</h3>
          <p className="sub">Tick what you really said. {suggested.length > 0 && 'Ticks marked “found” were detected in your words — check them.'}</p>
          <ul className="keypoints">
            {review.key_points.map((p, i) => (
              <li key={i}>
                <label>
                  <input type="checkbox" checked={covered.includes(i)}
                    onChange={() => setCovered((c) => (c.includes(i) ? c.filter((x) => x !== i) : [...c, i]))} />
                  <EnglishText text={p} />
                  {suggested.includes(i) && <small className="found">found</small>}
                </label>
              </li>
            ))}
          </ul>
          {answer && <details><summary>Your answer</summary><p className="your-answer">{answer}</p></details>}
          <h3>Model answer <ListenButton text={review.model_answer} refId={`iv:${q.id}`} /> <ListenButton text={review.model_answer} refId={`iv:${q.id}`} label="Slow" slow /></h3>
          <p className="model-answer"><EnglishText text={review.model_answer} termIds={q.glossary} /></p>
          <p className="sub">Shadowing: listen to one sentence, pause, and repeat it aloud with the same rhythm.</p>
          {review.follow_ups.length > 0 && (
            <>
              <h3>The interviewer may ask next</h3>
              <ul>{review.follow_ups.map((f) => <li key={f}><EnglishText text={f} /> <ListenButton text={f} refId={`iv:${q.id}`} label="" /></li>)}</ul>
            </>
          )}
          {review.docs.length > 0 && (
            <p className="docs">Read more: {review.docs.map((d) => <a key={d} href={d} target="_blank" rel="noreferrer">{d.replace(/^https?:\/\//, '')}</a>)}</p>
          )}
          <div className="actions">
            <button className="primary" disabled={saving} onClick={save}>
              {covered.length}/{review.key_points.length} points · {doneLabel}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

/* ---------- Practice tab ---------- */

export function InterviewPractice() {
  const [cats, setCats] = useState(null)
  const [stats, setStats] = useState(null)
  const [category, setCategory] = useState('')
  const [level, setLevel] = useState('')
  const [batch, setBatch] = useState(null)
  const [i, setI] = useState(0)
  const [done, setDone] = useState({ good: 0, total: 0 })

  const load = () => {
    api.interviewNext(category, level, 10).then((b) => { setBatch(b); setI(0); setDone({ good: 0, total: 0 }) })
    api.interviewCategories().then(setCats)
    api.interviewStats().then(setStats)
  }
  useEffect(load, [category, level])
  if (!batch || !cats || !stats) return <p>Loading…</p>
  const q = batch.questions[i]

  return (
    <section>
      <h1>Job interviews in English</h1>
      <p className="sub">
        Hear the question, answer aloud as in a real interview, then check which key points you
        covered and listen to a strong answer. Questions you answer weakly come back sooner.
      </p>
      <div className="tiles">
        <div className="tile"><b>{stats.answers}</b><span>answers practised ({stats.questions} questions)</span></div>
        <div className="tile"><b>{stats.words_per_minute ?? '—'}</b><span>your speaking pace (words/min, aim 110-150)</span></div>
        <div className="tile"><b>{stats.mocks[0] ? `${stats.mocks[0].score}%` : '—'}</b><span>last mock interview</span></div>
      </div>
      <div className="chips">
        <button className={!category ? 'active' : ''} onClick={() => setCategory('')}>All</button>
        {cats.map((c) => (
          <button key={c.id} className={category === c.id ? 'active' : ''} title={c.description} onClick={() => setCategory(c.id)}>
            {c.name} ({c.questions}){c.coverage != null && ` · ${c.coverage}%`}
          </button>
        ))}
      </div>
      <div className="toolbar">
        <select value={level} onChange={(e) => setLevel(e.target.value)}>
          <option value="">All levels</option>
          <option value="junior">Junior</option>
          <option value="mid">Mid</option>
          <option value="senior">Senior</option>
        </select>
        <span className="sub">{batch.due} due · {batch.unseen} new · session {done.good}/{done.total} good answers</span>
      </div>
      {!q ? (
        <div className="card done">
          <h2>Session complete</h2>
          <p>{done.good} of {done.total} answers covered most key points.</p>
          <button className="primary" onClick={load}>Practise more</button>
        </div>
      ) : (
        <AnswerCard key={q.id} q={q} number={`${i + 1}/${batch.questions.length}`}
          onDone={(r) => { setDone((d) => ({ good: d.good + (r.good ? 1 : 0), total: d.total + 1 })); setI(i + 1) }} />
      )}
    </section>
  )
}

/* ---------- Mock interview tab ---------- */

export function MockInterview() {
  const [cats, setCats] = useState([])
  const [chosen, setChosen] = useState([])
  const [count, setCount] = useState(8)
  const [session, setSession] = useState(null)
  const [i, setI] = useState(0)
  const [now, setNow] = useState(Date.now())
  const [startedAt, setStartedAt] = useState(null)
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])

  useEffect(() => { api.interviewCategories().then(setCats); api.interviewStats().then((s) => setHistory(s.mocks)) }, [])
  useEffect(() => {
    if (!session || result) return
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [session, result])

  const start = async () => {
    const s = await api.interviewMockStart({ questions: count, categories: chosen })
    setSession(s); setI(0); setResult(null); setStartedAt(Date.now()); setNow(Date.now())
  }
  const finish = async () => setResult(await api.interviewMockFinish(session.session_id))

  if (result) {
    return (
      <section>
        <h1>Mock interview result</h1>
        <div className="tiles">
          <div className="tile"><b>{result.score}%</b><span>key points covered</span></div>
          <div className="tile"><b>{result.words_per_minute ?? '—'}</b><span>words per minute</span></div>
          <div className="tile"><b>{result.questions.filter((q) => q.answered).length}/{result.questions.length}</b><span>questions answered</span></div>
        </div>
        <table>
          <thead><tr><th>#</th><th>Question</th><th>Type</th><th>Points</th><th>Time</th></tr></thead>
          <tbody>
            {result.questions.map((q, k) => (
              <tr key={q.question_id}>
                <td>{k + 1}</td><td>{q.question}</td><td>{label[q.type]}</td>
                <td>{q.answered ? `${q.covered}/${q.total}` : 'skipped'}</td>
                <td>{q.seconds ? fmt(q.seconds) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="sub">Practise the weak questions again in the Practice tab: they come back first.</p>
        <div className="actions"><button className="primary" onClick={() => { setSession(null); setResult(null) }}>New mock interview</button></div>
      </section>
    )
  }

  if (session) {
    const q = session.questions[i]
    const left = session.minutes * 60 - Math.round((now - startedAt) / 1000)
    return (
      <section>
        <div className="mock-head">
          <span>Mock interview · question {Math.min(i + 1, session.questions.length)}/{session.questions.length}</span>
          <span className={`timer ${left < 120 ? 'low' : ''}`}>{left >= 0 ? fmt(left) : `-${fmt(-left)}`}</span>
          <button className="link" onClick={finish}>Finish interview now</button>
        </div>
        {q ? (
          <AnswerCard key={q.id} q={q} number={`${i + 1}/${session.questions.length}`} sessionId={session.session_id}
            doneLabel={i + 1 < session.questions.length ? 'Next question' : 'Save and see result'}
            onDone={() => (i + 1 < session.questions.length ? setI(i + 1) : finish())} />
        ) : null}
        <p className="sub">“Finish interview now” ends the interview: questions you did not answer score 0.</p>
      </section>
    )
  }

  return (
    <section>
      <h1>Mock interview</h1>
      <p className="sub">
        A timed interview: it opens with a behavioral question, then mixes topics. Each question is
        read aloud; answer in English without pausing the clock. You get your score at the end.
      </p>
      {history.length > 0 && <p className="history">Last scores: {history.map((h) => <span key={h.id} className={h.score >= 70 ? 'ok' : 'ko'}>{h.score}%</span>)}</p>}
      <div className="card">
        <h3>Topics</h3>
        <div className="chips">
          {cats.map((c) => (
            <button key={c.id} className={chosen.includes(c.id) ? 'active' : ''}
              onClick={() => setChosen((x) => (x.includes(c.id) ? x.filter((y) => y !== c.id) : [...x, c.id]))}>
              {c.name}
            </button>
          ))}
        </div>
        <p className="sub">{chosen.length ? `${chosen.length} topics selected` : 'No topic selected = all topics.'}</p>
        <div className="actions">
          <label>Questions{' '}
            <select value={count} onChange={(e) => setCount(+e.target.value)}>
              <option value={5}>5 (~15 min)</option>
              <option value={8}>8 (~25 min)</option>
              <option value={12}>12 (~40 min)</option>
            </select>
          </label>
          <button className="primary" onClick={start}>Start mock interview</button>
        </div>
      </div>
    </section>
  )
}

/* ---------- Phrases tab ---------- */

export function Phrases() {
  const [groups, setGroups] = useState(null)
  const [es, setEs] = useState({})
  useEffect(() => { api.interviewPhrases().then(setGroups) }, [])
  if (!groups) return <p>Loading…</p>
  return (
    <section>
      <h1>Useful interview phrases</h1>
      <p className="sub">Listen, repeat aloud, and use them in your practice answers. Spanish only when you need it.</p>
      {groups.map((g) => (
        <div key={g.id} className="card phrase-group">
          <h2>{g.name}</h2>
          <p className="sub">{g.when}</p>
          <ul className="phrases">
            {g.phrases.map((p, k) => {
              const key = `${g.id}:${k}`
              return (
                <li key={key}>
                  <ListenButton text={p.text} refId={`phrase:${g.id}`} label="" />
                  <span><EnglishText text={p.text} />{p.note && <small className="sub"> · {p.note}</small>}</span>
                  {es[key] ? <em className="es">{p.es}</em>
                    : <button className="link" onClick={() => { setEs({ ...es, [key]: true }); api.englishEvent('translation', `phrase:${g.id}`).catch(() => {}) }}>ES</button>}
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </section>
  )
}
