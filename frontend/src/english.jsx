import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { api } from './api.js'

/* English support used everywhere (KCNA questions, CKA labs, mock exam):
   - technical terms (glossary.yaml) and general exam words (vocabulary.yaml) are highlighted
   - click one: simple English definition, example, 🔊 pronunciation, Spanish only on demand
   - every lookup / translation / listen is recorded, so the dashboard can show progress */

export const EnglishContext = createContext({ glossary: [], vocabulary: [], cert: null })
export const useEnglish = () => useContext(EnglishContext)

const log = (kind, ref) => api.englishEvent(kind, ref).catch(() => {})

/* ---------- text to speech (browser voices, works offline on macOS) ---------- */

export function speak(text, rate = 0.9) {
  if (!('speechSynthesis' in window)) return false
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text.replace(/`/g, '').replace(/\*\*/g, ''))
  u.lang = 'en-US'
  u.rate = rate
  const voice = window.speechSynthesis.getVoices().find((v) => v.lang === 'en-US' && /Samantha|Alex|Google US/.test(v.name))
    || window.speechSynthesis.getVoices().find((v) => v.lang?.startsWith('en'))
  if (voice) u.voice = voice
  window.speechSynthesis.speak(u)
  return true
}

export function ListenButton({ text, refId, label = 'Listen', slow = false }) {
  if (!('speechSynthesis' in window)) return null
  return (
    <button className="listen" type="button" title="Listen (US English)"
      onClick={(e) => { e.stopPropagation(); speak(text, slow ? 0.75 : 0.9); log('listen', refId) }}>
      🔊 {label}
    </button>
  )
}

/* ---------- find terms and words in a text ---------- */

function buildForms(glossary, vocabulary, termIds, cert) {
  // explicit ids (questions) win; otherwise skip terms meant for other certifications ("workflow", "bucket")
  const terms = termIds ? glossary.filter((t) => termIds.includes(t.id))
    : glossary.filter((t) => !t.certs?.length || !cert || t.certs.includes(cert))
  const forms = [
    ...terms.flatMap((t) => (t.match?.length ? t.match : [t.term]).map((m) => ({ m, item: { kind: 'term', ...t } }))),
    ...vocabulary.flatMap((w) => w.match.map((m) => ({ m, item: { kind: 'word', ...w } }))),
  ].sort((a, b) => b.m.length - a.m.length)
  if (!forms.length) return null
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const re = new RegExp(`\\b(${forms.map((f) => esc(f.m)).join('|')})\\b`, 'gi')
  const byForm = new Map(forms.map((f) => [f.m.toLowerCase(), f.item]))
  return { re, byForm }
}

function useForms(termIds) {
  const { glossary, vocabulary, cert } = useEnglish()
  const key = termIds ? termIds.join(',') : '*'
  return useMemo(() => buildForms(glossary, vocabulary, termIds, cert), [glossary, vocabulary, key, cert])
}

/** Items (terms first, then words) that appear in a text, without duplicates. */
export function useItemsIn(text, termIds) {
  const forms = useForms(termIds)
  return useMemo(() => {
    if (!forms || !text) return []
    const seen = new Map()
    for (const m of text.matchAll(forms.re)) {
      const item = forms.byForm.get(m[0].toLowerCase())
      const key = `${item.kind}:${item.id}`
      if (!seen.has(key)) seen.set(key, item)
    }
    return [...seen.values()].sort((a, b) => (a.kind === b.kind ? 0 : a.kind === 'term' ? -1 : 1))
  }, [forms, text])
}

/* ---------- highlighted text ---------- */

/** Text with clickable technical terms (dashed) and exam words (dotted).
 *  termIds: limit technical terms to these ids (KCNA questions); omit to use all terms (labs). */
export function EnglishText({ text, termIds, onTranslate }) {
  const forms = useForms(termIds)
  const [open, setOpen] = useState(null)
  useEffect(() => {
    if (open === null) return
    const close = (e) => { if (!e.target.closest('.term-wrap')) setOpen(null) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const parts = useMemo(() => {
    if (!forms || !text) return [text]
    const out = []
    let last = 0
    for (const m of text.matchAll(forms.re)) {
      out.push(text.slice(last, m.index), { word: m[0], item: forms.byForm.get(m[0].toLowerCase()), key: m.index })
      last = m.index + m[0].length
    }
    out.push(text.slice(last))
    return out
  }, [text, forms])

  const toggle = (p) => {
    const next = open === p.key ? null : p.key
    setOpen(next)
    if (next !== null) log('glossary_lookup', refOf(p.item))
  }

  return (
    <span>
      {parts.map((p, i) =>
        typeof p === 'string' ? p : (
          <span key={p.key} className="term-wrap">
            {/* span, not button: terms can appear inside option buttons */}
            <span className={p.item.kind === 'term' ? 'term' : 'word'} role="button" tabIndex={0}
              onClick={(e) => { e.stopPropagation(); toggle(p) }}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); toggle(p) } }}
            >{p.word}</span>
            {open === p.key && (
              <span className="popover" role="dialog" onClick={(e) => e.stopPropagation()}>
                <WordCard item={p.item} onTranslate={onTranslate} />
                <button className="link close" onClick={() => setOpen(null)}>close</button>
              </span>
            )}
          </span>
        ),
      )}
    </span>
  )
}

const refOf = (item) => (item.kind === 'word' ? `word:${item.id}` : item.id)

export function WordCard({ item, onTranslate }) {
  const [showEs, setShowEs] = useState(false)
  const name = item.kind === 'word' ? item.word : item.term
  return (
    <span className="word-card">
      <span className="wc-head">
        <strong>{name}</strong>
        <span className={`kind ${item.kind}`}>{item.kind === 'term' ? 'technical term' : 'exam English'}</span>
        <ListenButton text={name} refId={refOf(item)} label="" />
      </span>
      <span>{item.definition}</span>
      {item.example && <em className="example">“{item.example}”</em>}
      {showEs ? <em className="es">ES: {item.es}</em> : (
        <button className="link" onClick={(e) => {
          e.stopPropagation(); setShowEs(true); onTranslate?.(); log('translation', refOf(item))
        }}>Show in Spanish</button>
      )}
    </span>
  )
}

/* ---------- the visible English help bar under a question or task ---------- */

export function EnglishBar({ text, speakText, termIds, onTranslate }) {
  const items = useItemsIn(text, termIds)
  const [open, setOpen] = useState(null)
  return (
    <div className="english-bar">
      <div className="eb-row">
        <span className="eb-label">English help</span>
        <ListenButton text={speakText || text} refId="text" />
        <ListenButton text={speakText || text} refId="text-slow" label="Slow" slow />
        {items.length > 0 && <span className="eb-hint">Key words:</span>}
        {items.map((it) => {
          const k = `${it.kind}:${it.id}`
          return (
            <button key={k} className={`chip ${it.kind} ${open === k ? 'active' : ''}`}
              onClick={() => { const next = open === k ? null : k; setOpen(next); if (next) log('glossary_lookup', refOf(it)) }}>
              {it.kind === 'word' ? it.word : it.term}
            </button>
          )
        })}
      </div>
      {open && (() => {
        const it = items.find((x) => `${x.kind}:${x.id}` === open)
        return it ? <div className="eb-card"><WordCard key={open} item={it} onTranslate={onTranslate} /></div> : null
      })()}
    </div>
  )
}

/* ---------- English tab: vocabulary practice with spaced repetition ---------- */

export function EnglishPage() {
  const [stats, setStats] = useState(null)
  const [kind, setKind] = useState('')
  const [batch, setBatch] = useState(null)
  const [i, setI] = useState(0)
  const [result, setResult] = useState(null)
  const [score, setScore] = useState({ ok: 0, total: 0 })

  const loadStats = () => api.englishStats().then(setStats)
  const load = () => {
    api.englishNext(kind || undefined, 10).then((b) => { setBatch(b); setI(0); setResult(null); setScore({ ok: 0, total: 0 }) })
    loadStats()
  }
  useEffect(load, [kind])

  if (!batch || !stats) return <p>Loading…</p>
  const item = batch.items[i]
  const answer = async (opt) => {
    if (result) return
    const r = await api.englishAnswer(item.id, opt)
    setResult({ ...r, selected: opt })
    setScore((s) => ({ ok: s.ok + (r.correct ? 1 : 0), total: s.total + 1 }))
  }
  const next = () => { setI(i + 1); setResult(null) }
  const ev = stats.events || {}

  return (
    <section>
      <h1>English for the exams</h1>
      <p className="sub">
        The KCNA and CKA are only in English. Practise the technical terms and the everyday exam
        words you meet in the questions and labs. Words you looked up come first.
      </p>
      <div className="tiles">
        <div className="tile"><b>{stats.mastered}/{stats.items}</b><span>words mastered ({stats.terms} technical, {stats.words} exam English)</span></div>
        <div className="tile"><b>{ev.glossary_lookup || 0}</b><span>words looked up while studying</span></div>
        <div className="tile"><b>{ev.translation || 0}</b><span>times you needed Spanish (goal: fewer each week)</span></div>
        <div className="tile"><b>{ev.listen || 0}</b><span>times you listened to the pronunciation</span></div>
      </div>

      <div className="toolbar">
        <select value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">All words</option>
          <option value="term">Technical terms</option>
          <option value="word">Exam English</option>
        </select>
        <span className="sub">{batch.due} due · {batch.unseen} new · session {score.ok}/{score.total}</span>
      </div>

      {!item ? (
        <div className="card done">
          <h2>Session complete</h2>
          <p>You got {score.ok} of {score.total} right. Missed words come back sooner.</p>
          <button className="primary" onClick={load}>Practise more</button>
        </div>
      ) : (
        <div className="card">
          <div className="meta">
            <span>Word {i + 1}/{batch.items.length}</span>
            <span>{item.kind === 'term' ? 'technical term' : 'exam English'}</span>
            {item.looked_up > 0 && <span>you looked this up {item.looked_up}×</span>}
          </div>
          <p className="question">Which word matches this meaning?</p>
          <p className="definition">“{item.definition}”</p>
          {item.example && <p className="example">Example: {item.example}</p>}
          <ul className="options">
            {item.options.map((o) => {
              const right = result && o.toLowerCase() === result.word.toLowerCase()
              const wrong = result && o === result.selected && !result.correct
              return (
                <li key={o}>
                  <button className={[right && 'right', wrong && 'wrong'].filter(Boolean).join(' ')} disabled={!!result} onClick={() => answer(o)}>
                    {o}
                  </button>
                </li>
              )
            })}
          </ul>
          {result && (
            <div className={`feedback ${result.correct ? 'ok' : 'ko'}`}>
              <strong>{result.correct ? 'Correct.' : `Not quite — it is “${result.word}”.`}</strong>
              <p><WordCard item={{ ...result, kind: result.kind, term: result.word }} /></p>
            </div>
          )}
          <div className="actions">
            {result && <button className="primary" onClick={next}>Next</button>}
          </div>
        </div>
      )}

      {stats.most_looked_up.length > 0 && (
        <>
          <h2>Words you look up most</h2>
          <p className="sub">These are your weak words. Read the definition aloud, then practise them above.</p>
          <dl className="glossary">
            {stats.most_looked_up.map((w) => (
              <div key={w.id}>
                <dt>{w.word} <small className="sub">· {w.count}×</small> <ListenButton text={w.word} refId={w.id} label="" /></dt>
                <dd>{w.definition}</dd>
              </div>
            ))}
          </dl>
        </>
      )}
    </section>
  )
}
