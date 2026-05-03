import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.backtesting.service import BacktestService
from app.config import get_settings
from app.db.models import MarketBar, MarketFeature, MovementAlert
from app.db.session import get_engine, get_session_factory

router = APIRouter()


def get_session_dep():
    settings = get_settings()
    engine = get_engine(settings.database_url)
    factory = get_session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@router.get("/alerts")
def get_alerts(
    severity: str | None = None,
    limit: int = Query(default=50, le=200),
    session: Session = Depends(get_session_dep),
):
    query = session.query(MovementAlert).order_by(MovementAlert.created_at.desc())
    if severity:
        query = query.filter(MovementAlert.severity == severity)
    return [_alert_to_dict(a) for a in query.limit(limit).all()]


@router.get("/tickers/{ticker}/signals")
def get_ticker_signals(ticker: str, session: Session = Depends(get_session_dep)):
    alerts = session.query(MovementAlert).filter(MovementAlert.ticker == ticker).order_by(MovementAlert.timestamp.desc()).limit(50).all()
    features = session.query(MarketFeature).filter(MarketFeature.ticker == ticker).order_by(MarketFeature.timestamp.desc()).limit(60).all()
    bars = session.query(MarketBar).filter(MarketBar.ticker == ticker).order_by(MarketBar.timestamp.desc()).limit(60).all()
    return {
        "ticker": ticker,
        "alerts": [_alert_to_dict(a) for a in alerts],
        "features": [_feature_to_dict(f) for f in features],
        "bars": [_bar_to_dict(b) for b in bars],
    }


@router.post("/backtests")
def run_backtest(request: dict, session: Session = Depends(get_session_dep)):
    svc = BacktestService(lambda: session)
    result = svc.run(request["start_date"], request["end_date"])
    return {
        "start_date": result.start_date,
        "end_date": result.end_date,
        "total_alerts": result.total_alerts,
        "alerts_by_severity": result.alerts_by_severity,
        "alerts_by_signal_type": result.alerts_by_signal_type,
        "alerts_per_day": result.alerts_per_day,
        "top_alerts": result.top_alerts,
    }


def _alert_to_dict(a: MovementAlert) -> dict:
    return {
        "id": a.id,
        "ticker": a.ticker,
        "timestamp": a.timestamp.isoformat(),
        "severity": a.severity,
        "signal_type": a.signal_type,
        "score": a.score,
        "explanation": a.explanation,
        "metrics": json.loads(a.metrics) if a.metrics else {},
        "created_at": a.created_at.isoformat(),
    }


def _feature_to_dict(f: MarketFeature) -> dict:
    return {
        "ticker": f.ticker,
        "interval": f.interval,
        "timestamp": f.timestamp.isoformat(),
        "return_pct": f.return_pct,
        "gap_pct": f.gap_pct,
        "volume_ratio": f.volume_ratio,
        "relative_volume": f.relative_volume,
        "return_zscore_60d": f.return_zscore_60d,
        "volume_zscore_60d": f.volume_zscore_60d,
        "gap_percentile_60d": f.gap_percentile_60d,
    }


def _bar_to_dict(b: MarketBar) -> dict:
    return {
        "ticker": b.ticker,
        "interval": b.interval,
        "timestamp": b.timestamp.isoformat(),
        "open": b.open,
        "high": b.high,
        "low": b.low,
        "close": b.close,
        "volume": b.volume,
        "vwap": b.vwap,
    }
