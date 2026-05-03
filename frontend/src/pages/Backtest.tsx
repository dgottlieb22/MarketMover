import { useState } from 'react'
import { runBacktest } from '../api'

export default function Backtest() {
  const [startDate, setStartDate] = useState('2025-01-01')
  const [endDate, setEndDate] = useState('2025-04-30')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<any>(null)

  const handleRun = async () => {
    setRunning(true)
    try {
      const data = await runBacktest(startDate, endDate)
      setResult(data)
    } catch (e: any) {
      setResult({ error: e.message })
    } finally {
      setRunning(false)
    }
  }

  return (
    <div>
      <h1>Backtest</h1>

      <div className='card'>
        <div className='form-row'>
          <label>Start:</label>
          <input type='date' value={startDate} onChange={e => setStartDate(e.target.value)} />
          <label>End:</label>
          <input type='date' value={endDate} onChange={e => setEndDate(e.target.value)} />
          <button onClick={handleRun} disabled={running}>
            {running ? 'Running...' : 'Run Backtest'}
          </button>
        </div>
      </div>

      {result && !result.error && (
        <>
          <div className='stats-grid'>
            <div className='stat-card'>
              <div className='stat-value'>{result.total_alerts}</div>
              <div className='stat-label'>Total Alerts</div>
            </div>
            <div className='stat-card'>
              <div className='stat-value'>{result.alerts_per_day}</div>
              <div className='stat-label'>Alerts / Day</div>
            </div>
            {Object.entries(result.alerts_by_severity || {}).map(([k, v]) => (
              <div key={k} className='stat-card'>
                <div className='stat-value'>{v as number}</div>
                <div className='stat-label'>{k}</div>
              </div>
            ))}
          </div>

          <div className='card'>
            <h2>By Signal Type</h2>
            <div className='stats-grid'>
              {Object.entries(result.alerts_by_signal_type || {}).map(([k, v]) => (
                <div key={k} className='stat-card'>
                  <div className='stat-value'>{v as number}</div>
                  <div className='stat-label'>{k}</div>
                </div>
              ))}
            </div>
          </div>

          {result.top_alerts?.length > 0 && (
            <div className='card'>
              <h2>Top Alerts</h2>
              <table>
                <thead>
                  <tr><th>#</th><th>Ticker</th><th>Date</th><th>Type</th><th>Score</th><th>Severity</th></tr>
                </thead>
                <tbody>
                  {result.top_alerts.map((a: any, i: number) => (
                    <tr key={i}>
                      <td>{i + 1}</td>
                      <td>{a.ticker}</td>
                      <td>{a.timestamp.slice(0, 10)}</td>
                      <td>{a.signal_type}</td>
                      <td>{a.score.toFixed(1)}</td>
                      <td><span className={`badge ${a.severity}`}>{a.severity}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {result?.error && <div className='status error'>❌ {result.error}</div>}
    </div>
  )
}
