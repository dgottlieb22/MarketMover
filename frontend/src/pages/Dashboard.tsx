import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { runPipeline, getAlerts } from '../api'

interface Alert {
  id: string
  ticker: string
  timestamp: string
  severity: string
  signal_type: string
  score: number
  explanation: string
}

const PRESETS: Record<string, string> = {
  'Mag 7': 'AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA',
  'Tech 20': 'AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,AMD,CRM,ORCL,ADBE,QCOM,AVGO,INTC,MU,AMAT,NFLX,SNPS,CDNS,TXN',
  'Meme': 'GME,AMC,BBBY,PLTR,SOFI,HOOD,COIN,MARA,RIOT,LCID',
  'Fintech': 'SQ,PYPL,COIN,HOOD,SOFI,AFRM,NU,MELI,GRAB,SE',
  'Cyber': 'CRWD,PANW,ZS,FTNT,NET,S,OKTA,CYBR,TENB,QLYS',
  'Semis': 'NVDA,AMD,INTC,AVGO,QCOM,TXN,MU,AMAT,LRCX,KLAC,MRVL,ON,ADI,NXPI,MCHP',
  'AI': 'NVDA,MSFT,GOOGL,META,AMD,AVGO,PLTR,AI,SNOW,DDOG,MDB,PATH,SMCI,ARM,MRVL,DELL,VRT,CRWV,IONQ,RGTI',
}

export default function Dashboard() {
  const [tickers, setTickers] = useState(() => localStorage.getItem('mmd_tickers') ?? 'AAPL,TSLA,NVDA,GME,AMD')
  const [days, setDays] = useState(() => Number(localStorage.getItem('mmd_days')) || 120)
  const [provider, setProvider] = useState(() => localStorage.getItem('mmd_provider') ?? 'yahoo')

  useEffect(() => { localStorage.setItem('mmd_tickers', tickers) }, [tickers])
  useEffect(() => { localStorage.setItem('mmd_days', String(days)) }, [days])
  useEffect(() => { localStorage.setItem('mmd_provider', provider) }, [provider])
  const [running, setRunning] = useState(false)
  const [runResult, setRunResult] = useState<any>(null)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [filter, setFilter] = useState<string | null>(null)
  const [limit, setLimit] = useState(25)

  const loadAlerts = async () => {
    const data = await getAlerts(filter ?? undefined, limit)
    setAlerts(data)
  }

  useEffect(() => { loadAlerts() }, [filter, limit])

  const handleRun = async () => {
    setRunning(true)
    setRunResult(null)
    try {
      const result = await runPipeline(tickers, days, provider)
      setRunResult(result)
      await loadAlerts()
    } catch (e: any) {
      setRunResult({ error: e.message })
    } finally {
      setRunning(false)
    }
  }

  const exportCsv = () => {
    const header = 'Ticker,Date,Severity,Score,Signal Type,Explanation'
    const rows = alerts.map(a =>
      `${a.ticker},${a.timestamp.slice(0, 10)},${a.severity},${a.score},"${a.signal_type}","${a.explanation.replace(/"/g, '""')}"`
    )
    const blob = new Blob([header + '\n' + rows.join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `alerts-${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <h1>Market Movement Detector</h1>

      <div className='card'>
        <h2>Run Pipeline</h2>
        <div className='form-row'>
          <label>Tickers:</label>
          <input
            value={tickers}
            onChange={e => setTickers(e.target.value)}
            style={{ width: '300px' }}
            placeholder='AAPL,TSLA,NVDA'
          />
        </div>
        <div className='form-row'>
          {Object.entries(PRESETS).map(([name, list]) => (
            <button
              key={name}
              className={`filter-btn ${tickers === list ? 'active' : ''}`}
              onClick={() => setTickers(list)}
            >
              {name} ({list.split(',').length})
            </button>
          ))}
        </div>
        <div className='form-row'>
          <label>Days:</label>
          <input
            type='number'
            value={days}
            onChange={e => setDays(Number(e.target.value))}
            style={{ width: '80px' }}
          />
          <label>Provider:</label>
          <select value={provider} onChange={e => setProvider(e.target.value)}>
            <option value='yahoo'>Yahoo Finance</option>
            <option value='mock'>Mock</option>
          </select>
          <button onClick={handleRun} disabled={running}>
            {running ? 'Running...' : 'Run Pipeline'}
          </button>
        </div>
        {running && <div className='status loading'>Fetching data and running detection...</div>}
        {runResult && !runResult.error && (
          <div className='status success'>
            ✅ {runResult.status} — {runResult.bars_ingested} bars ingested, {runResult.alerts_generated} alerts generated
            (high: {runResult.alerts_by_severity?.high ?? 0}, medium: {runResult.alerts_by_severity?.medium ?? 0}, low: {runResult.alerts_by_severity?.low ?? 0})
          </div>
        )}
        {runResult?.error && <div className='status error'>❌ {runResult.error}</div>}
      </div>

      <div className='card'>
        <h2>Alerts</h2>
        <div className='filter-row'>
          {[null, 'high', 'medium', 'low'].map(s => (
            <button
              key={s ?? 'all'}
              className={`filter-btn ${filter === s ? 'active' : ''}`}
              onClick={() => setFilter(s)}
            >
              {s ?? 'All'}
            </button>
          ))}
          <span style={{ borderLeft: '1px solid #2d333b', margin: '0 0.25rem' }} />
          <label style={{ fontSize: '0.8rem', color: '#8b949e' }}>Show:</label>
          {[10, 25, 50, 100].map(n => (
            <button
              key={n}
              className={`filter-btn ${limit === n ? 'active' : ''}`}
              onClick={() => setLimit(n)}
            >
              {limit === n ? `Show ${n}` : n}
            </button>
          ))}
          {alerts.length > 0 && <>
            <span style={{ borderLeft: '1px solid #2d333b', margin: '0 0.25rem' }} />
            <button className='filter-btn' onClick={exportCsv}>Export CSV</button>
          </>}
        </div>
        {alerts.length === 0 && <p style={{ color: '#8b949e' }}>No alerts. Run the pipeline to generate alerts.</p>}
        {(() => {
          const groups: Record<string, Alert[]> = {}
          for (const a of alerts) {
            const key = `${a.ticker}:${a.timestamp.slice(0, 10)}`
            ;(groups[key] ??= []).push(a)
          }
          return Object.values(groups).map(group => {
            const best = group.reduce((a, b) => a.score >= b.score ? a : b)
            const date = best.timestamp.slice(0, 10)
            const today = new Date().toISOString().slice(0, 10)
            const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10)
            const recency = date === today ? 'today' : date === yesterday ? 'yesterday' : date
            const isRecent = date === today || date === yesterday
            return (
            <div key={`${best.ticker}-${date}`} className='alert-item'>
              <div className='alert-header'>
                <span className={`badge ${best.severity}`}>{best.severity}</span>
                <Link to={`/ticker/${best.ticker}`} className='ticker-link'>{best.ticker}</Link>
                <span className='score'>score={best.score.toFixed(1)}</span>
                {group.map(a => (
                  <span key={a.signal_type} className='signal-badge'>{a.signal_type}</span>
                ))}
                <span className={`alert-date${isRecent ? ' recent' : ''}`}>{recency}</span>
              </div>
              <div className='explanation'>{best.explanation}</div>
            </div>
            )
          })
        })()}
      </div>
    </div>
  )
}
