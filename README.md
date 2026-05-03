# Unusual Market Movement Detector

A market-data pipeline that ingests OHLCV data, computes rolling statistical baselines, and flags equities whose price or volume behavior is unusual relative to their own recent history.

This is an engineering exploration of time-series ingestion, feature computation, and explainable anomaly detection — not a trading system.

## Architecture

```
Market Data Provider
        │
        ▼
  Ingestion Service ──► Raw OHLCV Store
        │
        ▼
  Feature Computation ──► Feature Store
        │
        ▼
  Anomaly Detection
        │
   ┌────┴────┐
   ▼         ▼
Alert Store  API
```

**Components:**
- **Ingestion Service** — Fetches bars from a pluggable provider, upserts into DB with idempotent merge
- **Feature Computation** — Computes return %, gap %, volume ratios, rolling z-scores, gap percentiles
- **Anomaly Detection** — Rule-based detection for price moves, volume spikes, gaps, and combined signals
- **Alert Store** — Deduplicated alerts with severity scoring and template-based explanations
- **API** — FastAPI endpoints for alerts, ticker signals, and backtesting

## Example Alert

> SPIKE is up 15.0%, which is 4.2 standard deviations above its 60-day average return. Volume is 10.3x its normal level.

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

## Local Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Run Tests

```bash
python3 -m pytest tests/ -v
```

### Run API Server

```bash
uvicorn app.api.app:app --reload
```

### Docker Compose

```bash
docker compose up
```

This starts PostgreSQL and the API server. The API is available at `http://localhost:8000/api/v1/`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/alerts` | List alerts, optional `?severity=high&limit=50` |
| GET | `/api/v1/tickers/{ticker}/signals` | Alerts, features, and bars for a ticker |
| POST | `/api/v1/backtests` | Run backtest with `{"start_date": "...", "end_date": "..."}` |

## Project Structure

```
backend/
├── app/
│   ├── api/          # FastAPI routes and app factory
│   ├── ingestion/    # Provider interface, mock provider, ingestion service
│   ├── features/     # Rolling statistical feature computation
│   ├── detection/    # Rule-based anomaly detection engine
│   ├── backtesting/  # Historical backtest runner
│   ├── db/           # SQLAlchemy models and session management
│   └── config.py     # Pydantic settings with env var support
├── tests/
│   ├── test_unit.py         # 40 unit tests
│   └── test_integration.py  # 8 integration tests
└── pyproject.toml
```

## Known Limitations

- Uses SQLite for development; PostgreSQL recommended for production
- Mock provider only; no real market data provider implemented yet
- No frontend dashboard
- Batch processing only; no streaming support
- No split adjustment or corporate action handling

## Future Work

- Real market data providers (Polygon, Alpha Vantage, Yahoo Finance)
- Sector-relative movement detection
- Intraday bar support with alert deduplication
- Streaming ingestion with Kafka/Kinesis
- React dashboard
- ML-based anomaly detection comparison
