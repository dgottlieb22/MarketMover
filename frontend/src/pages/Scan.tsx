import { useState } from 'react'
import { Link } from 'react-router-dom'
import { screenTickers, runScan } from '../api'

export default function Scan() {
  const [price, setPrice] = useState('over10')
  const [volume, setVolume] = useState('over500k')
  const [marketCap, setMarketCap] = useState('any')
  const [screening, setScreening] = useState(false)
  const [tickers, setTickers] = useState<string[]>([])
  const [scanning, setScanning] = useState(false)
  const [progress, setProgress] = useState({ processed: 0, total: 0 })
  const [result, setResult] = useState<any>(null)

  const handleScreen = async () => {
    setScreening(true)
    setTickers([])
    setResult(null)
    try {
      const data = await screenTickers({ price, volume, market_cap: marketCap })
      setTickers(data.tickers)
    } finally {
      setScreening(false)
    }
  }

  const handleScan = async () => {
    setScanning(true)
    setResult(null)
    setProgress({ processed: 0, total: tickers.length })
    try {
      const data = await runScan(tickers, 120, (p) => {
        setProgress({ processed: p.processed, total: p.total })
      })
      setResult(data)
    } finally {
      setScanning(false)
    }
  }

  const pct = progress.total > 0 ? Math.round((progress.processed / progress.total) * 100) : 0

  return (
    <div>
      <h1>Market Scan</h1>

      <div className='card'>
        <h2>1. Screen Universe</h2>
        <div className='form-row'>
          <label>Min Price:</label>
          <select value={price} onChange={e => setPrice(e.target.value)}>
            <option value='any'>Any</option>
            <option value='over1'>Over $1</option>
            <option value='over5'>Over $5</option>
            <option value='over10'>Over $10</option>
            <option value='over20'>Over $20</option>
            <option value='over50'>Over $50</option>
          </select>
          <label>Min Avg Volume:</label>
          <select value={volume} onChange={e => setVolume(e.target.value)}>
            <option value='any'>Any</option>
            <option value='over100k'>Over 100K</option>
            <option value='over500k'>Over 500K</option>
            <option value='over1m'>Over 1M</option>
            <option value='over5m'>Over 5M</option>
          </select>
          <label>Market Cap:</label>
          <select value={marketCap} onChange={e => setMarketCap(e.target.value)}>
            <option value='any'>Any</option>
            <option value='mega'>Mega ($200B+)</option>
            <option value='large'>Large ($10B-$200B)</option>
            <option value='mid'>Mid ($2B-$10B)</option>
            <option value='small'>Small ($300M-$2B)</option>
            <option value='mid+'>Mid+ (over $2B)</option>
            <option value='small+'>Small+ (over $300M)</option>
          </select>
          <button onClick={handleScreen} disabled={screening}>
            {screening ? 'Screening...' : 'Screen'}
          </button>
        </div>
        {screening && (
          <div className='status loading'>
            Screening Finviz for matching tickers... this may take 30-60 seconds depending on filters.
            <div className='spinner' />
          </div>
        )}
        {tickers.length > 0 && (
          <div className='status success'>
            Found {tickers.length} tickers matching filters
          </div>
        )}
      </div>

      {tickers.length > 0 && (
        <div className='card'>
          <h2>2. Run Detection</h2>
          <p style={{ color: '#8b949e', fontSize: '0.9rem', marginBottom: '0.75rem' }}>
            Scan {tickers.length} tickers for unusual movement (processes in batches of 50)
          </p>
          <button onClick={handleScan} disabled={scanning}>
            {scanning ? `Scanning... ${pct}%` : `Scan ${tickers.length} Tickers`}
          </button>
          {scanning && (
            <div style={{ marginTop: '0.75rem' }}>
              <div style={{
                background: '#21262d', borderRadius: '4px', height: '8px', overflow: 'hidden',
              }}>
                <div style={{
                  background: '#58a6ff', height: '100%', width: `${pct}%`,
                  transition: 'width 0.3s',
                }} />
              </div>
              <div style={{ fontSize: '0.8rem', color: '#8b949e', marginTop: '0.25rem' }}>
                {progress.processed} / {progress.total} tickers processed
              </div>
            </div>
          )}
        </div>
      )}

      {result && (
        <div className='card'>
          <h2>Results</h2>
          <div className='stats-grid'>
            <div className='stat-card'>
              <div className='stat-value'>{result.total_scanned}</div>
              <div className='stat-label'>Scanned</div>
            </div>
            <div className='stat-card'>
              <div className='stat-value'>{result.alerts_found}</div>
              <div className='stat-label'>Alerts Found</div>
            </div>
          </div>

          {result.alerts?.length > 0 && (
            <table>
              <thead>
                <tr><th>Ticker</th><th>Date</th><th>Severity</th><th>Score</th><th>Signal</th><th>Explanation</th></tr>
              </thead>
              <tbody>
                {result.alerts.map((a: any, i: number) => (
                  <tr key={i}>
                    <td><Link to={`/ticker/${a.ticker}`} className='ticker-link'>{a.ticker}</Link></td>
                    <td>{a.date}</td>
                    <td><span className={`badge ${a.severity}`}>{a.severity}</span></td>
                    <td>{a.score.toFixed(1)}</td>
                    <td><span className='signal-badge'>{a.signal_type}</span></td>
                    <td style={{ maxWidth: '350px', fontSize: '0.85rem' }}>{a.explanation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {result.alerts?.length === 0 && (
            <p style={{ color: '#8b949e' }}>No unusual movement detected across {result.total_scanned} tickers.</p>
          )}
        </div>
      )}
    </div>
  )
}
