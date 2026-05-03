import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.backtesting.service import BacktestService
from app.config import get_settings
from app.db.models import MarketBar, MarketFeature, MovementAlert
from app.db.session import get_engine, get_session_factory, init_db
from app.detection.engine import DetectionEngine
from app.features.service import FeatureService
from app.ingestion.service import IngestionService

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
    query = session.query(MovementAlert).order_by(MovementAlert.timestamp.desc(), MovementAlert.score.desc())
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


SECTOR_MAP: dict[str, str] = {
    "AAPL": "XLK", "MSFT": "XLK", "GOOGL": "XLK", "META": "XLK", "CRM": "XLK",
    "ORCL": "XLK", "ADBE": "XLK", "INTC": "XLK", "CSCO": "XLK",
    "NVDA": "SMH", "AMD": "SMH", "AVGO": "SMH", "QCOM": "SMH", "TXN": "SMH",
    "MU": "SMH", "AMAT": "SMH", "LRCX": "SMH", "KLAC": "SMH", "MRVL": "SMH",
    "ARM": "SMH", "SMCI": "SMH", "ON": "SMH", "ADI": "SMH", "NXPI": "SMH",
    "TSLA": "QQQ", "AMZN": "QQQ", "NFLX": "QQQ",
    "JPM": "XLF", "GS": "XLF", "MS": "XLF", "BAC": "XLF", "WFC": "XLF",
    "V": "XLF", "MA": "XLF", "BLK": "XLF", "SCHW": "XLF", "AXP": "XLF",
    "XOM": "XLE", "CVX": "XLE", "COP": "XLE", "SLB": "XLE", "OXY": "XLE",
    "UNH": "XLV", "JNJ": "XLV", "PFE": "XLV", "MRK": "XLV", "LLY": "XLV",
    "CRWD": "HACK", "PANW": "HACK", "ZS": "HACK", "FTNT": "HACK", "NET": "HACK",
    "GME": "IWM", "AMC": "IWM", "PLTR": "QQQ", "COIN": "QQQ", "HOOD": "QQQ",
}


@router.get("/tickers/{ticker}/benchmark")
def get_benchmark(ticker: str, session: Session = Depends(get_session_dep)):
    """Return benchmark ETF returns alongside ticker returns for comparison."""
    benchmark = SECTOR_MAP.get(ticker.upper(), "SPY")
    bars = session.query(MarketBar).filter(
        MarketBar.ticker == ticker
    ).order_by(MarketBar.timestamp).all()

    if len(bars) < 2:
        return {"ticker": ticker, "benchmark": benchmark, "comparisons": []}

    # Fetch benchmark bars from Yahoo on-demand
    from app.ingestion.yahoo_provider import YahooFinanceProvider
    provider = YahooFinanceProvider()
    bench_bars = provider.get_bars(benchmark, bars[0].timestamp, bars[-1].timestamp, "1d")
    bench_by_date = {b.timestamp.date(): b for b in bench_bars}

    comparisons = []
    for i in range(1, len(bars)):
        prev, cur = bars[i - 1], bars[i]
        ret = (cur.close - prev.close) / prev.close
        d = cur.timestamp.date()
        bench_bar = bench_by_date.get(d)
        prev_date = prev.timestamp.date()
        bench_prev = bench_by_date.get(prev_date)
        bench_ret = None
        if bench_bar and bench_prev and bench_prev.close:
            bench_ret = (bench_bar.close - bench_prev.close) / bench_prev.close
        comparisons.append({
            "date": d.isoformat(),
            "ticker_return": round(ret * 100, 2),
            "benchmark_return": round(bench_ret * 100, 2) if bench_ret is not None else None,
            "relative": round((ret - (bench_ret or 0)) * 100, 2),
        })

    return {"ticker": ticker, "benchmark": benchmark, "comparisons": comparisons}


COMMON_TICKERS = [
    "AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","AMD","CRM","ORCL",
    "ADBE","QCOM","AVGO","INTC","MU","AMAT","NFLX","SNPS","CDNS","TXN",
    "GME","AMC","PLTR","SOFI","HOOD","COIN","MARA","RIOT","LCID","RIVN",
    "SQ","PYPL","AFRM","NU","MELI","GRAB","SE","SHOP","DDOG","SNOW",
    "CRWD","PANW","ZS","FTNT","NET","OKTA","CYBR","TENB","QLYS","S",
    "LRCX","KLAC","MRVL","ON","ADI","NXPI","MCHP","ARM","SMCI","VRT",
    "AI","MDB","PATH","DELL","IONQ","RGTI","BABA","JD","PDD","NIO",
    "BA","CAT","DE","GE","HON","LMT","RTX","UNP","UPS","FDX",
    "JPM","GS","MS","BAC","WFC","C","BLK","SCHW","AXP","V","MA",
    "UNH","JNJ","PFE","MRK","ABBV","LLY","TMO","ABT","BMY","GILD",
    "DIS","CMCSA","T","VZ","TMUS","ROKU","SPOT","RBLX","U","TTWO",
    "XOM","CVX","COP","SLB","OXY","MPC","VLO","PSX","EOG","PXD",
    "SPY","QQQ","IWM","DIA","SMH","XLF","XLE","XLK","ARKK","SOXX",
]


@router.get("/tickers/search")
def search_tickers(q: str = Query(default="", min_length=1)):
    q = q.upper()
    matches = [t for t in COMMON_TICKERS if t.startswith(q)]
    return matches[:10]


@router.post("/run")
def run_pipeline(request: dict):
    settings = get_settings()

    # Allow UI to override detection thresholds
    for key in ['price_zscore_threshold', 'volume_ratio_threshold', 'combined_zscore_threshold',
                'combined_volume_threshold', 'severity_low', 'severity_medium', 'severity_high']:
        if key in request:
            setattr(settings, key, float(request[key]))

    engine = get_engine(settings.database_url)
    init_db(engine)
    factory = get_session_factory(engine)

    tickers = [t.strip().upper() for t in request.get("tickers", "AAPL,TSLA,NVDA").split(",")]
    days = request.get("days", 120)
    provider_name = request.get("provider", "yahoo")

    if provider_name == "yahoo":
        from app.ingestion.yahoo_provider import YahooFinanceProvider
        provider = YahooFinanceProvider()
    else:
        from app.ingestion.mock_provider import MockProvider
        provider = MockProvider()

    end = datetime.now()
    start = end - timedelta(days=days)

    # Clear old data for these tickers to prevent mixed-provider contamination
    with factory() as session:
        for model in [MovementAlert, MarketFeature, MarketBar]:
            session.query(model).filter(model.ticker.in_(tickers)).delete(synchronize_session=False)
        session.commit()

    svc = IngestionService(factory, provider)
    svc.ingest(tickers, start, end)

    feat_svc = FeatureService(factory, settings)
    det = DetectionEngine(factory, settings)
    all_alerts = []
    for t in tickers:
        feat_svc.compute_features(t)
        all_alerts.extend(det.detect(t))

    with factory() as session:
        bars_count = session.query(MarketBar).filter(
            MarketBar.ticker.in_(tickers)
        ).count()

    return {
        "status": "success",
        "tickers": tickers,
        "bars_ingested": bars_count,
        "alerts_generated": len(all_alerts),
        "alerts_by_severity": {
            s: len([a for a in all_alerts if a.severity == s])
            for s in ["high", "medium", "low"]
        },
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
