import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'

/* A stopwatch that restarts when `key` changes and does not count time while the tab is hidden. */
export function useStopwatch(key) {
  const t = useRef({ start: 0, hiddenAt: null, hidden: 0, first: null })
  useEffect(() => { t.current = { start: performance.now(), hiddenAt: null, hidden: 0, first: null } }, [key])
  useEffect(() => {
    const onVis = () => {
      const s = t.current
      if (document.hidden) s.hiddenAt = performance.now()
      else if (s.hiddenAt != null) { s.hidden += performance.now() - s.hiddenAt; s.hiddenAt = null }
    }
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [])
  const elapsed = () => (performance.now() - t.current.start - t.current.hidden) / 1000
  return {
    elapsed,
    markFirst: () => { if (t.current.first == null) t.current.first = elapsed() },
    first: () => t.current.first,
  }
}

/* One line after a practice question: how fast you read and answered it. */
export function ReadingLine({ r, budget }) {
  if (!r) return null
  return (
    <p className="reading-line muted small">
      ⏱ Read in {r.read_seconds} s (<b>{r.wpm} wpm</b>) · answered in {r.answer_seconds} s
      {budget ? ` · the real exam gives about ${budget} s per question` : ''}
    </p>
  )
}

const VERDICT = {
  good: 'In time for the real exam',
  watch: 'Close to the limit: practise reading faster',
  slow: 'Too slow for the real exam',
}

/* Dashboard tile: median reading speed and answer time of recent practice. */
export function ReadingTile({ examId }) {
  const [p, setP] = useState(null)
  useEffect(() => { api.reading(examId).then(setP).catch(() => {}) }, [examId])
  if (!p) return null
  return (
    <div className={`tile reading-tile ${p.verdict}`} title={`Median of your last ${p.samples} practice answers. ` +
      `A comfortable pace in a second language is about ${p.comfort_wpm} words per minute.`}>
      <b>{p.wpm ?? '—'}{p.wpm ? ' wpm' : ''}</b>
      <span>reading speed{p.answer_seconds != null ? ` · ${p.answer_seconds} s per answer (exam: ${p.budget_seconds} s)` : ''}</span>
      <span className="small">{p.verdict === 'unknown' ? `${p.samples} of 10 answers measured` : VERDICT[p.verdict]}</span>
    </div>
  )
}
