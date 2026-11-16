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

/* "Explain more" under a practice question, after it is checked. */
export function ExplainMore({ q, selected }) {
  const [state, setState] = useState('idle')   // idle | asking | loading | done | error
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
  if (state === 'idle') {
    return (
      <div className="ai-explain">
        <button className="ai-button" onClick={run}>✨ Explain more (AI)</button>
        <button className="link" onClick={() => setState('asking')}>Ask a question about it</button>
      </div>
    )
  }
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
