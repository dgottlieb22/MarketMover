import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getTickerSignals, getBenchmark } from '../api'

function PriceChart({ bars, alertDates }: { bars: any[]; alertDates: Set<string> }) {
  const W = 900, H = 200, PAD = 40
  const closes = bars.map((b: any) => b.close)
  const min = Math.min(...closes), max = Math.max(...closes)
  const range = max - min || 1
  const xStep = (W - PAD * 2) / (bars.length - 1)

  const points = closes.map((c: number, i: number) => {
    const x = PAD + i * xStep
    const y = H - PAD - ((c - min) / range) * (H - PAD * 2)
    return { x, y, bar: bars[i] }
  })

  const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ')

  return (
    <div className='card'>
      <h2>Price Chart</h2>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto' }}>
        {/* grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map(pct => {
          const y = H - PAD - pct * (H - PAD * 2)
          const val = min + pct * range
          return <g key={pct}>
            <line x1={PAD} y1={y} x2={W - PAD} y2={y} stroke='#2d333b' strokeWidth={0.5} />
            <text x={PAD - 4} y={y + 3} textAnchor='end' fill='#6e7681' fontSize={9}>${val.toFixed(0)}</text>
          </g>
        })}
        {/* price line */}
        <path d={line} fill='none' stroke='#58a6ff' strokeWidth={1.5} />
        {/* alert markers */}
        {points.filter(p => alertDates.has(p.bar.timestamp.slice(0, 10))).map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={4} fill='#da3633' stroke='#0f1117' strokeWidth={1.5} />
        ))}
        {/* x-axis labels */}
        {points.filter((_, i) => i % Math.ceil(bars.length / 6) === 0).map((p, i) => (
          <text key={i} x={p.x} y={H - 8} textAnchor='middle' fill='#6e7681' fontSize={9}>
            {p.bar.timestamp.slice(5, 10)}
          </text>
        ))}
      </svg>
      <div style={{ fontSize: '0.75rem', color: '#6e7681', marginTop: '0.25rem' }}>
        <span style={{ color: '#da3633' }}>●</span> = alert triggered
      </div>
    </div>
  )
}

export default function TickerDetail() {
  const { ticker } = useParams<{ ticker: string }>()
  const [data, setData] = useState<any>(null)
  const [bench, setBench] = useState<any>(null)

  useEffect(() => {
    if (ticker) {
      getTickerSignals(ticker).then(setData)
      getBenchmark(ticker).then(setBench).catch(() => {})
    }
  }, [ticker])

  if (!data) return <p>Loading...</p>

  // Bars are newest-first from API; reverse for chronological charts
  const bars = [...data.bars].reverse()
  const alertDates = new Set<string>(data.alerts.map((a: any) => a.timestamp.slice(0, 10)))

  return (
    <div>
      <Link to='/' className='back-link'>← Back to Dashboard</Link>
      <h1>{ticker} Signals</h1>

      {bars.length > 1 && <PriceChart bars={bars} alertDates={alertDates} />}

      {bench?.comparisons?.length > 0 && (
        <div className='card'>
          <h2>vs {bench.benchmark} (last 10 days)</h2>
          <table>
            <thead>
              <tr><th>Date</th><th>{ticker}</th><th>{bench.benchmark}</th><th>Relative</th></tr>
            </thead>
            <tbody>
              {bench.comparisons.slice(-10).reverse().map((c: any) => (
                <tr key={c.date}>
                  <td>{c.date}</td>
                  <td style={{ color: c.ticker_return >= 0 ? '#3fb950' : '#f85149' }}>
                    {c.ticker_return >= 0 ? '+' : ''}{c.ticker_return}%
                  </td>
                  <td style={{ color: (c.benchmark_return ?? 0) >= 0 ? '#3fb950' : '#f85149' }}>
                    {c.benchmark_return != null ? `${c.benchmark_return >= 0 ? '+' : ''}${c.benchmark_return}%` : '—'}
                  </td>
                  <td style={{ color: c.relative >= 0 ? '#3fb950' : '#f85149', fontWeight: 600 }}>
                    {c.relative >= 0 ? '+' : ''}{c.relative}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className='card'>
        <h2>Alerts ({data.alerts.length})</h2>
        {data.alerts.length === 0 && <p style={{ color: '#8b949e' }}>No alerts for this ticker.</p>}
        <table>
          <thead>
            <tr><th>Date</th><th>Type</th><th>Score</th><th>Severity</th><th>Explanation</th></tr>
          </thead>
          <tbody>
            {data.alerts.map((a: any) => (
              <tr key={a.id}>
                <td>{a.timestamp.slice(0, 10)}</td>
                <td>{a.signal_type}</td>
                <td>{a.score.toFixed(1)}</td>
                <td><span className={`badge ${a.severity}`}>{a.severity}</span></td>
                <td style={{ maxWidth: '400px' }}>{a.explanation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className='card'>
        <h2>Features (last 60 days)</h2>
        <table>
          <thead>
            <tr><th>Date</th><th>Return%</th><th>Z-Score</th><th>RelVol</th><th>VolZ</th><th>GapPctl</th></tr>
          </thead>
          <tbody>
            {data.features.map((f: any, i: number) => (
              <tr key={i}>
                <td>{f.timestamp.slice(0, 10)}</td>
                <td>{f.return_pct != null ? (f.return_pct * 100).toFixed(2) + '%' : '—'}</td>
                <td>{f.return_zscore_60d?.toFixed(2) ?? '—'}</td>
                <td>{f.relative_volume?.toFixed(2) ?? '—'}</td>
                <td>{f.volume_zscore_60d?.toFixed(2) ?? '—'}</td>
                <td>{f.gap_percentile_60d?.toFixed(0) ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className='card'>
        <h2>Price History</h2>
        <table>
          <thead>
            <tr><th>Date</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th></tr>
          </thead>
          <tbody>
            {data.bars.map((b: any, i: number) => (
              <tr key={i}>
                <td>{b.timestamp.slice(0, 10)}</td>
                <td>{b.open.toFixed(2)}</td>
                <td>{b.high.toFixed(2)}</td>
                <td>{b.low.toFixed(2)}</td>
                <td>{b.close.toFixed(2)}</td>
                <td>{(b.volume / 1e6).toFixed(1)}M</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
