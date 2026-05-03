import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getTickerSignals } from '../api'

export default function TickerDetail() {
  const { ticker } = useParams<{ ticker: string }>()
  const [data, setData] = useState<any>(null)

  useEffect(() => {
    if (ticker) getTickerSignals(ticker).then(setData)
  }, [ticker])

  if (!data) return <p>Loading...</p>

  return (
    <div>
      <Link to='/' className='back-link'>← Back to Dashboard</Link>
      <h1>{ticker} Signals</h1>

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
