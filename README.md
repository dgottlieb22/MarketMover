# Unusual Market Movement Detector

A market-data pipeline that ingests OHLCV data, computes rolling statistical baselines, and flags equities whose price or volume behavior is unusual relative to their own recent history.

This is an engineering exploration of time-series ingestion, feature computation, and explainable anomaly detection — not a trading system.

## Architecture

```
Market Data Provider (Yahoo Finance)
        │
        ▼
  Ingestion Service ──► Raw OHLCV Store (SQLite/Postgres)
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

Go to **http://localhost:5173** in your browser. From there you can:
- Enter tickers and run the pipeline (fetches real data from Yahoo Finance)
- Browse and filter alerts by severity
- Click a ticker to see its signals, features, and price history
- Run backtests over historical date ranges

### CLI Alternative

You can also run the pipeline from the command line:

```bash
cd backend
source .venv/bin/activate

# Run with real Yahoo Finance data
python -m app.cli run -t "AAPL,TSLA,GME"

# Run with mock data
python -m app.cli run -p mock

# View stored alerts
python -m app.cli alerts -s high
```

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

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/run` | Run the full pipeline for given tickers |
| GET | `/api/v1/alerts` | List alerts, optional `?severity=high&limit=50` |
| GET | `/api/v1/tickers/{ticker}/signals` | Alerts, features, and bars for a ticker |
| POST | `/api/v1/backtests` | Run backtest with `{"start_date": "...", "end_date": "..."}` |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routes and app factory
│   │   ├── ingestion/    # Provider interface, Yahoo Finance, mock provider
│   │   ├── features/     # Rolling statistical feature computation
│   │   ├── detection/    # Rule-based anomaly detection engine
│   │   ├── backtesting/  # Historical backtest runner
│   │   ├── db/           # SQLAlchemy models and session management
│   │   ├── cli.py        # CLI for running the pipeline
│   │   └── config.py     # Pydantic settings with env var support
│   ├── handler.py        # AWS Lambda handler
│   └── tests/            # 55 tests (unit + integration + provider/CLI)
├── frontend/
│   └── src/
│       ├── pages/        # Dashboard, TickerDetail, Backtest
│       ├── api.ts        # API client
│       └── App.tsx       # Router and layout
├── infra/                # AWS CDK stack (VPC, RDS, ECS, Lambda, SNS, S3)
└── docker-compose.yml
```

## Known Limitations

- Uses SQLite for development; PostgreSQL recommended for production
- Yahoo Finance data is free but unofficial — can break if Yahoo changes their site
- Batch processing only; no streaming support
- No split adjustment or corporate action handling

## Future Work

- Sector-relative movement detection
- Intraday bar support with alert deduplication
- Streaming ingestion with Kafka/Kinesis
- ML-based anomaly detection comparison
