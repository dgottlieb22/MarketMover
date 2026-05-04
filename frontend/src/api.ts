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

export async function getBenchmark(ticker: string) {
  const res = await fetch(`${BASE}/tickers/${ticker}/benchmark`)
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

export async function screenTickers(
  filters: Record<string, string>,
  onProgress?: (page: number, total: number) => void,
): Promise<{ count: number; tickers: string[] }> {
  const res = await fetch(`${BASE}/scan/screen`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(filters),
  })
  const reader = res.body?.getReader()
  if (!reader) throw new Error('No response body')
  const decoder = new TextDecoder()
  let buffer = ''
  let result = { count: 0, tickers: [] as string[] }
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.trim()) continue
      const data = JSON.parse(line)
      if (data.type === 'progress' && onProgress) onProgress(data.page, data.total_pages)
      if (data.type === 'done') result = { count: data.count, tickers: data.tickers }
    }
  }
  return result
}

export async function runScan(
  tickers: string[],
  days: number,
  onProgress: (data: any) => void,
): Promise<any> {
  const res = await fetch(`${BASE}/scan/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tickers, days }),
  })
  const reader = res.body?.getReader()
  const decoder = new TextDecoder()
  let result = null
  if (!reader) throw new Error('No response body')
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.trim()) continue
      const data = JSON.parse(line)
      if (data.type === 'progress') onProgress(data)
      if (data.type === 'done') result = data
    }
  }
  return result
}
