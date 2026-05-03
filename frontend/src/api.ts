const BASE = '/api/v1'

async function handleResponse(res: Response) {
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function searchTickers(q: string): Promise<string[]> {
  if (!q) return []
  const res = await fetch(`${BASE}/tickers/search?q=${encodeURIComponent(q)}`)
  return handleResponse(res)
}

export async function runPipeline(tickers: string, days: number, provider: string, overrides?: Record<string, number>) {
  const res = await fetch(`${BASE}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tickers, days, provider, ...overrides }),
  })
  return handleResponse(res)
}

export async function getAlerts(severity?: string, limit = 50) {
  const params = new URLSearchParams()
  if (severity) params.set('severity', severity)
  params.set('limit', String(limit))
  const res = await fetch(`${BASE}/alerts?${params}`)
  return handleResponse(res)
}

export async function getTickerSignals(ticker: string) {
  const res = await fetch(`${BASE}/tickers/${ticker}/signals`)
  return handleResponse(res)
}

export async function runBacktest(startDate: string, endDate: string) {
  const res = await fetch(`${BASE}/backtests`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ start_date: startDate, end_date: endDate }),
  })
  return handleResponse(res)
}
