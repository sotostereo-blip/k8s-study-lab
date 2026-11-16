import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'

/* Mock exam history: one small line chart per kind of mock exam (multiple choice, labs),
   the passing score as a dashed line, and the per-domain trend (first vs. average of the last 3). */
export default function History({ certId }) {
  const [data, setData] = useState(null)
  useEffect(() => { api.history(certId).then(setData).catch(() => setData(null)) }, [certId])
  if (!data) return null
  const shown = data.series.filter((s) => s.points.length > 0)
  return (
    <div className="history-block">
      <h2>Mock exam history</h2>
      {shown.length === 0 && <p className="muted">Take a mock exam: your scores over time will show here.</p>}
      {shown.map((s) => <Series key={s.kind} s={s} />)}
    </div>
  )
}

const fmtDay = (ts) => new Date(ts.replace(' ', 'T') + 'Z').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

function Series({ s }) {
  const last = s.points.at(-1)
  const best = Math.max(...s.points.map((p) => p.score))
  const trends = s.domains.filter((d) => d.count > 0)
  return (
    <div className="card history-series">
      <div className="history-head">
        <h3>{s.label}</h3>
        <span className="muted small">{s.points.length} taken · last {last.score}% · best {best}% · pass {s.passing_score}%</span>
      </div>
      <ScoreChart points={s.points} passing={s.passing_score} label={s.label} />
      {trends.length > 0 && (
        <div className="table-scroll"><table className="trend">
          <thead><tr><th>Domain</th><th>Weight</th><th>First</th><th>Recent</th><th>Change</th></tr></thead>
          <tbody>
            {trends.map((d) => (
              <tr key={d.id}>
                <td>{d.name}</td>
                <td>{d.weight}%</td>
                <td>{d.first}%</td>
                <td><b>{d.recent}%</b></td>
                <td className={d.change > 0 ? 'up' : d.change < 0 ? 'down' : ''}>
                  {d.change == null ? '—' : d.change > 0 ? `▲ +${d.change}` : d.change < 0 ? `▼ ${d.change}` : '= 0'}
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
      {trends.length > 0 && <p className="muted small">Recent = the average of your last 3 mock exams in that domain.</p>}
      <details className="small">
        <summary>Show every mock exam as a table</summary>
        <table>
          <thead><tr><th>#</th><th>Date</th><th>Score</th><th>Result</th></tr></thead>
          <tbody>
            {s.points.map((p, i) => (
              <tr key={i}><td>{i + 1}</td><td>{fmtDay(p.date)}</td><td>{p.score}%</td>
                <td>{p.score >= s.passing_score ? '✓ pass' : '✗ below pass'}</td></tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}

const H = 200, PAD = { l: 40, r: 16, t: 12, b: 26 }

function ScoreChart({ points, passing, label }) {
  const [hover, setHover] = useState(null)
  const [W, setW] = useState(640)    // drawn at its real width, so the text keeps its size on a phone
  const svg = useRef(null)
  const box = useRef(null)
  useEffect(() => {
    const ro = new ResizeObserver(([e]) => setW(Math.max(260, Math.round(e.contentRect.width))))
    ro.observe(box.current)
    return () => ro.disconnect()
  }, [])
  const n = points.length
  const x = (i) => PAD.l + (n === 1 ? (W - PAD.l - PAD.r) / 2 : (i * (W - PAD.l - PAD.r)) / (n - 1))
  const y = (v) => PAD.t + ((100 - v) * (H - PAD.t - PAD.b)) / 100
  const line = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.score).toFixed(1)}`).join(' ')
  const move = (e) => {
    const r = svg.current.getBoundingClientRect()
    const px = ((e.clientX - r.left) / r.width) * W
    let best = 0
    points.forEach((_, i) => { if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i })
    setHover(best)
  }
  const hp = hover != null ? points[hover] : null
  const labelEvery = Math.ceil(n / Math.max(3, Math.floor(W / 80)))
  return (
    <div className="score-chart" ref={box}>
      <svg ref={svg} viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label={`${label}: ${points.map((p) => `${p.score}%`).join(', ')}; passing score ${passing}%`}
        onMouseMove={move} onMouseLeave={() => setHover(null)}>
        {[0, 25, 50, 75, 100].map((v) => (
          <g key={v}>
            <line className="grid" x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} />
            <text className="axis" x={PAD.l - 8} y={y(v) + 4} textAnchor="end">{v}%</text>
          </g>
        ))}
        <line className="pass" x1={PAD.l} x2={W - PAD.r} y1={y(passing)} y2={y(passing)} />
        <text className="axis pass-label" x={PAD.l + 6} y={y(passing) - 5}>pass {passing}%</text>
        {points.map((p, i) => (i % labelEvery === 0 || i === n - 1) && (
          <text key={i} className="axis" x={x(i)} y={H - 6} textAnchor="middle">{i + 1}</text>
        ))}
        {hp && <line className="crosshair" x1={x(hover)} x2={x(hover)} y1={PAD.t} y2={H - PAD.b} />}
        <path className="series" d={line} />
        {points.map((p, i) => (
          <circle key={i} className={`dot ${i === hover ? 'on' : ''}`} cx={x(i)} cy={y(p.score)} r={i === hover ? 6 : 4.5} />
        ))}
        <text className="axis value" x={x(n - 1)} y={y(points[n - 1].score) - 10} textAnchor={n > 1 ? 'end' : 'middle'}>
          {points[n - 1].score}%
        </text>
      </svg>
      {hp && (
        <div className="chart-tip" style={{ left: `${Math.min(85, Math.max(15, (x(hover) / W) * 100))}%`,
          ...(hp.score > 55 ? { top: 'auto', bottom: '34px' } : {}) }}>
          <b>Mock exam {hover + 1}</b> · {fmtDay(hp.date)}<br />
          {hp.score}% · {hp.score >= passing ? 'pass' : `${(passing - hp.score).toFixed(1)} below pass`}
        </div>
      )}
    </div>
  )
}
