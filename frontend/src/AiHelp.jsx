import { useEffect, useState } from 'react'
import { api } from './api.js'

/* Optional AI help (only when the backend has an Anthropic API key). */

let statusPromise = null
export function useAiEnabled() {
  const [on, setOn] = useState(false)
  useEffect(() => {
    statusPromise ||= api.aiStatus().catch(() => ({ enabled: false }))
    statusPromise.then((s) => setOn(!!s.enabled))
  }, [])
  return on
}

/* AI text: paragraphs, ```code blocks```, `inline code` and **bold**. */
export function AiText({ text }) {
  if (!text) return null
  return text.split(/```[a-zA-Z0-9]*\n?([\s\S]*?)```/g).map((part, i) => (
    i % 2 === 1
      ? <pre key={i} className="ai-code">{part.replace(/\n$/, '')}</pre>
      : part.trim().split(/\n\s*\n/).filter(Boolean).map((p, k) => (
        <p key={`${i}-${k}`}>{p.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).map((s, j) => (
          s.startsWith('`') && s.endsWith('`') && s.length > 1 ? <code key={j}>{s.slice(1, -1)}</code>
            : s.startsWith('**') && s.endsWith('**') && s.length > 4 ? <b key={j}>{s.slice(2, -2)}</b>
              : s))}</p>
      ))
  ))
}

/* The AI buttons under a practice question, after it is checked. */
export function AiTools({ q, selected }) {
  const [mode, setMode] = useState(null)   // null | more | ask | it
  if (mode === 'more' || mode === 'ask') return <ExplainMore q={q} selected={selected} startAsking={mode === 'ask'} />
  if (mode === 'it') return <ExplainIt q={q} onClose={() => setMode(null)} />
  return (
    <div className="ai-explain">
      <button className="ai-button" onClick={() => setMode('more')}>✨ Explain more (AI)</button>
      <button className="ai-button" onClick={() => setMode('it')}>✍️ Explain it in English (AI)</button>
      <button className="link" onClick={() => setMode('ask')}>Ask a question about it</button>
    </div>
  )
}

/* "Explain more": a longer explanation, optionally answering the student's own question. */
function ExplainMore({ q, selected, startAsking }) {
  const [state, setState] = useState(startAsking ? 'asking' : 'loading')   // asking | loading | done | error
  const [ask, setAsk] = useState('')
  const [ex, setEx] = useState(null)
  const [error, setError] = useState(null)
  const [showAnswer, setShowAnswer] = useState(false)
  const run = async () => {
    setState('loading'); setError(null); setShowAnswer(false)
    try {
      setEx(await api.practiceExplain({ question_id: q.id, selected, ask: ask.trim() || null }))
      setState('done')
    } catch (e) {
      setError(e.message); setState('error')
    }
  }
  useEffect(() => { if (!startAsking) run() }, [])   // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="ai-explain card">
      {(state === 'asking' || state === 'error') && (
        <form onSubmit={(e) => { e.preventDefault(); run() }}>
          <label className="small">Your question (in English or Spanish), optional
            <textarea rows={2} maxLength={1000} value={ask} onChange={(e) => setAsk(e.target.value)}
              placeholder="For example: when would I use a DaemonSet instead?" />
          </label>
          <button className="ai-button" type="submit">✨ Explain more (AI)</button>
        </form>
      )}
      {state === 'loading' && <p className="muted"><span className="spinner" /> The AI tutor is writing an explanation…</p>}
      {error && <p className="error">{error}</p>}
      {state === 'done' && ex && (
        <>
          <p className="ai-label">AI tutor · {ex.model}</p>
          {ex.answer_to_student && <div className="ai-answer"><b>Your question</b><AiText text={ex.answer_to_student} /></div>}
          <h4>The idea</h4><AiText text={ex.idea} />
          <h4>Why the right answer is right</h4><AiText text={ex.why_right} />
          {ex.your_choice && <><h4>About your choice</h4><AiText text={ex.your_choice} /></>}
          <h4>Example</h4><AiText text={ex.example} />
          <p className="ai-remember">📌 <b>Remember:</b> {ex.remember}</p>
          <div className="ai-check">
            <b>Check yourself:</b> {ex.check_question}{' '}
            {showAnswer ? <p><AiText text={ex.check_answer} /></p>
              : <button className="link" onClick={() => setShowAnswer(true)}>Show the answer</button>}
          </div>
          <p className="muted small">AI can make mistakes: the official docs linked above are the reference.</p>
          <button className="link" onClick={() => { setState('asking'); setEx(null) }}>Ask another question</button>
        </>
      )}
    </div>
  )
}

const VERDICT = {
  correct: { label: 'Technically correct', cls: 'ok', icon: '✓' },
  partly: { label: 'Partly correct', cls: 'warn', icon: '◐' },
  wrong: { label: 'Not correct', cls: 'ko', icon: '✗' },
}

/* "Explain it": the student writes why the right answer is right; the AI checks the technical
   content and the English, and returns a corrected version. */
function ExplainIt({ q, onClose }) {
  const [text, setText] = useState('')
  const [state, setState] = useState('writing')   // writing | loading | done
  const [out, setOut] = useState(null)
  const [error, setError] = useState(null)
  const words = text.trim() ? text.trim().split(/\s+/).length : 0
  const send = async (e) => {
    e.preventDefault()
    setState('loading'); setError(null)
    try { setOut(await api.practiceExplainIt({ question_id: q.id, text })); setState('done') } catch (err) { setError(err.message); setState('writing') }
  }
  const v = out && VERDICT[out.verdict]
  return (
    <div className="ai-explain card">
      <h4>✍️ Explain it in English</h4>
      {state !== 'done' && (
        <form onSubmit={send}>
          <p className="small muted">Write 1 to 3 sentences: <i>why</i> is the right answer right? Explaining it in your own
            words is one of the best ways to remember it, and practises your technical English.</p>
          <textarea rows={4} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)}
            placeholder="The right answer is … because …" disabled={state === 'loading'} />
          <div className="actions">
            <button className="ai-button" type="submit" disabled={words < 8 || state === 'loading'}>
              {state === 'loading' ? 'Checking…' : 'Check my explanation'}
            </button>
            <span className="muted small">{words} words{words < 8 ? ' (8 or more)' : ''}</span>
            <button type="button" className="link" onClick={onClose}>Cancel</button>
          </div>
        </form>
      )}
      {error && <p className="error">{error}</p>}
      {state === 'done' && out && (
        <>
          <p className="ai-label">AI check · {out.model}</p>
          <p><span className={`verdict ${v.cls}`}>{v.icon} {v.label}</span>{' '}
            <span className={`verdict ${out.english_ok ? 'ok' : 'warn'}`}>{out.english_ok ? '✓ English OK' : '✎ English to fix'}</span></p>
          <blockquote className="your-text">{text}</blockquote>
          <AiText text={out.technical} />
          {out.missing.length > 0 && <><h4>Also say</h4><ul>{out.missing.map((m, i) => <li key={i}>{m}</li>)}</ul></>}
          {out.english.length > 0 && (
            <><h4>English</h4>
              <ul className="english-fixes">{out.english.map((f, i) => (
                <li key={i}><s>{f.said}</s> → <b>{f.better}</b> <span className="muted small">{f.why}</span></li>
              ))}</ul></>
          )}
          <h4>Your explanation, improved</h4>
          <p className="ai-remember">{out.better}</p>
          {out.stats && <p className="muted small">Explanations written: {out.stats.written} · technically correct: {out.stats.correct || 0} · with no English mistakes: {out.stats.english_ok || 0}</p>}
          <p className="muted small">AI can make mistakes: the official docs linked above are the reference.</p>
          <button className="link" onClick={() => { setState('writing'); setOut(null) }}>Try again</button>
        </>
      )}
    </div>
  )
}
