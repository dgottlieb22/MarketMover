# Unusual Market Movement Detector

A market-data pipeline that ingests OHLCV data, computes rolling statistical baselines, and flags equities whose price or volume behavior is unusual relative to their own recent history.

This is an engineering exploration of time-series ingestion, feature computation, and explainable anomaly detection — not a trading system.

## Architecture

```
Market Data Provider (Yahoo Finance)
        │
        ▼
  Ingestion Service ──► Raw OHLCV Store (SQLite)
        │
        ▼
  Feature Computation ──► Feature Store
        │
        ▼
  Anomaly Detection
        │
   ┌────┴────┐
   ▼         ▼
Alert Store  API ◄── React Dashboard
```

## Example Alert

> SPIKE is up 15.0%, which is 4.2 standard deviations above its 60-day average return. Volume is 10.3x its normal level.

## Quick Start

You need two terminals — one for the backend API, one for the frontend dev server.

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.api.app:app --reload
```

The API starts at `http://localhost:8000/api/v1/`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

The dashboard starts at `http://localhost:5173/`. It proxies API requests to the backend automatically.

### 3. Open the Dashboard

Go to **http://localhost:5173** in your browser.

## Dashboard Features

**Run Pipeline** — Enter tickers (or pick a preset universe), choose Yahoo Finance or Mock provider, and run the full ingestion → feature computation → detection pipeline.

- **Preset universes**: Mag 7, Tech 20, Meme, Fintech, Cyber, Semis, AI
- **Ticker autocomplete**: Type in the "Add ticker..." box to search 130+ common symbols
- **Detection tuning**: Click "Tuning ⚙" to adjust z-score and volume thresholds with sliders
- **Auto-refresh**: Toggle to re-run the pipeline every 5 minutes
- **Alert grouping**: Multiple signals for the same ticker+date are combined into one card
- **Severity filter**: Filter by high/medium/low, limit to 10/25/50/100 alerts
- **Export CSV**: Download alerts as a spreadsheet
- **Watchlist persistence**: Your tickers, days, and provider are saved across sessions

**Ticker Detail** — Click any ticker to see:
- SVG price chart with red markers on alert days
- Relative comparison vs sector ETF (e.g. NVDA vs SMH)
- Alerts, features, and price history tables

**Market Scan** — Scan the entire market using Finviz screener filters:
1. Set min price, avg volume, and market cap filters
2. Screen to find matching tickers (with live page-by-page progress)
3. Scan all matches for unusual movement (batches of 200, 30s delay between batches)
4. Results show only tickers that triggered alerts, sorted by score

**Backtest** — Run detection over a historical date range and see summary stats.

### CLI Alternative

```bash
cd backend && source .venv/bin/activate

# Run with real Yahoo Finance data
python -m app.cli run -t "AAPL,TSLA,GME"

# Run with mock data
python -m app.cli run -p mock

# View stored alerts
python -m app.cli alerts -s high
```

## Data Storage

Market data is stored in `backend/market_data.db` (SQLite). Data older than 3 days is automatically purged on each pipeline run. Configure with `MMD_DATA_RETENTION_DAYS` env var.

## Running Tests

```bash
# Backend (55 tests)
cd backend && source .venv/bin/activate
python3 -m pytest tests/ -v

# CDK infrastructure (12 tests)
cd infra && npm test
```

## Detection Methodology

Signals are triggered by simple, explainable statistical rules:

| Signal | Condition |
|--------|-----------|
| Price Move | \|return z-score\| ≥ 2.5 |
| Volume Spike | relative volume ≥ 3.0 or volume z-score ≥ 3.0 |
| Gap | gap percentile ≥ 95th or ≤ 5th |
| Combined | \|return z-score\| ≥ 2.0 AND relative volume ≥ 2.0 |

Anomaly score = 0.40 × return + 0.35 × volume + 0.15 × gap + 0.10 × volatility

Severity: **high** ≥ 85, **medium** ≥ 70, **low** ≥ 50.

All thresholds are adjustable from the dashboard UI.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/run` | Run the full pipeline for given tickers |
| GET | `/api/v1/alerts` | List alerts, optional `?severity=high&limit=50` |
| GET | `/api/v1/tickers/{ticker}/signals` | Alerts, features, and bars for a ticker |
| GET | `/api/v1/tickers/{ticker}/benchmark` | Relative comparison vs sector ETF |
| GET | `/api/v1/tickers/search?q=NV` | Ticker autocomplete search |
| POST | `/api/v1/backtests` | Run backtest over a date range |
| POST | `/api/v1/scan/screen` | Screen tickers via Finviz (streaming progress) |
| POST | `/api/v1/scan/run` | Run detection on screened tickers (streaming progress) |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routes, CORS, streaming endpoints
│   │   ├── ingestion/    # Provider interface, Yahoo Finance (batch), mock
│   │   ├── features/     # Rolling statistical feature computation
│   │   ├── detection/    # Rule-based anomaly detection engine
│   │   ├── backtesting/  # Historical backtest runner
│   │   ├── db/           # SQLAlchemy models, session management, cleanup
│   │   ├── cli.py        # CLI for running the pipeline
│   │   └── config.py     # Pydantic settings with env var support
│   ├── handler.py        # AWS Lambda handler
│   └── tests/            # 55 tests (unit + integration + provider/CLI)
├── frontend/
│   └── src/
│       ├── pages/        # Dashboard, TickerDetail, Backtest, Scan
│       ├── api.ts        # API client with streaming support
│       └── App.tsx       # Router and layout
├── infra/                # AWS CDK stack (VPC, RDS, ECS, Lambda, SNS, S3)
└── docker-compose.yml
```

## Known Limitations

- Uses SQLite for development; PostgreSQL recommended for production
- Yahoo Finance is free but unofficial — can rate-limit with large scans
- Large market scans (2000+ tickers) take 10-15 minutes due to Yahoo rate limiting
- Batch processing only; no streaming support
- No split adjustment or corporate action handling

## Future Work

- Intraday bar support with alert deduplication
- News context for alerts (pull headlines when a ticker is flagged)
- Streaming ingestion with Kafka/Kinesis
- ML-based anomaly detection comparison
