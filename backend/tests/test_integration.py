import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.routes import get_session_dep
from app.db.models import MarketBar, MarketFeature, MovementAlert


# ---------------------------------------------------------------------------
# 1. Full Pipeline Test
# ---------------------------------------------------------------------------
def test_full_pipeline(session_factory, settings):
    """Test: ingest -> compute features -> detect anomalies -> backtest"""
    from app.ingestion.mock_provider import MockProvider
    from app.ingestion.service import IngestionService
    from app.features.service import FeatureService
    from app.detection.engine import DetectionEngine
    from app.backtesting.service import BacktestService

    provider = MockProvider()
    start = datetime(2025, 1, 1)
    end = datetime(2025, 4, 30)  # ~85 trading days, enough for 60-day window
    tickers = ['AAPL', 'SPIKE']

    # Step 1: Ingest
    svc = IngestionService(session_factory, provider)
    run = svc.ingest(tickers, start, end)
    assert run.status == 'success'

    with session_factory() as s:
        bar_count = s.query(MarketBar).count()
        assert bar_count > 0

    # Step 2: Compute features
    feat_svc = FeatureService(session_factory, settings)
    for t in tickers:
        feat_svc.compute_features(t)

    with session_factory() as s:
        feat_count = s.query(MarketFeature).count()
        assert feat_count > 0

    # Step 3: Detect anomalies
    engine = DetectionEngine(session_factory, settings)
    all_alerts = []
    for t in tickers:
        alerts = engine.detect(t)
        all_alerts.extend(alerts)

    spike_alerts = [a for a in all_alerts if a.ticker == 'SPIKE']
    assert len(spike_alerts) > 0, 'SPIKE should trigger at least one alert'

    # Step 4: Backtest
    bt_svc = BacktestService(session_factory)
    result = bt_svc.run('2025-01-01', '2025-04-30')
    assert result.total_alerts > 0
    assert len(result.top_alerts) > 0


# ---------------------------------------------------------------------------
# 2. API Integration Tests
# ---------------------------------------------------------------------------
def _make_client(session):
    """Create a TestClient with session dependency overridden."""
    app = create_app()

    def override():
        yield session

    app.dependency_overrides[get_session_dep] = override
    return TestClient(app)


def test_api_get_alerts(session_factory, session):
    """Test GET /api/v1/alerts returns alerts from DB"""
    alert = MovementAlert(
        id='test-alert-1', ticker='TEST', timestamp=datetime(2025, 3, 15),
        severity='high', signal_type='price_move', score=90.0,
        explanation='TEST is up 10%.', metrics=json.dumps({'return_pct': 0.10}),
        created_at=datetime.now(UTC),
    )
    session.add(alert)
    session.commit()

    client = _make_client(session)
    resp = client.get('/api/v1/alerts')
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]['ticker'] == 'TEST'


def test_api_get_alerts_filter_severity(session_factory, session):
    """Test GET /api/v1/alerts?severity=high filters correctly"""
    for sev in ['high', 'low']:
        session.add(MovementAlert(
            id=f'alert-{sev}', ticker='TEST', timestamp=datetime(2025, 3, 15),
            severity=sev, signal_type='price_move', score=90.0 if sev == 'high' else 55.0,
            explanation='test', metrics='{}', created_at=datetime.now(UTC),
        ))
    session.commit()

    client = _make_client(session)
    resp = client.get('/api/v1/alerts?severity=high')
    assert resp.status_code == 200
    data = resp.json()
    assert all(a['severity'] == 'high' for a in data)


def test_api_get_ticker_signals(session_factory, session):
    """Test GET /api/v1/tickers/{ticker}/signals"""
    session.add(MarketBar(
        ticker='XYZ', interval='1d', timestamp=datetime(2025, 3, 15),
        open=100, high=105, low=99, close=103, volume=1000000,
        vwap=102.3, provider='test', ingested_at=datetime.now(UTC),
    ))
    session.commit()

    client = _make_client(session)
    resp = client.get('/api/v1/tickers/XYZ/signals')
    assert resp.status_code == 200
    data = resp.json()
    assert data['ticker'] == 'XYZ'
    assert 'alerts' in data
    assert 'features' in data
    assert 'bars' in data
    assert len(data['bars']) >= 1


def test_api_post_backtest(session_factory, session):
    """Test POST /api/v1/backtests"""
    client = _make_client(session)
    resp = client.post('/api/v1/backtests', json={'start_date': '2025-01-01', 'end_date': '2025-12-31'})
    assert resp.status_code == 200
    data = resp.json()
    assert 'total_alerts' in data
    assert 'alerts_by_severity' in data


# ---------------------------------------------------------------------------
# 3. Idempotency Test
# ---------------------------------------------------------------------------
def test_ingestion_idempotency(session_factory):
    """Ingesting same data twice should not create duplicates"""
    from app.ingestion.mock_provider import MockProvider
    from app.ingestion.service import IngestionService

    provider = MockProvider()
    start = datetime(2025, 3, 1)
    end = datetime(2025, 3, 15)
    svc = IngestionService(session_factory, provider)

    svc.ingest(['AAPL'], start, end)
    with session_factory() as s:
        count1 = s.query(MarketBar).count()

    svc.ingest(['AAPL'], start, end)
    with session_factory() as s:
        count2 = s.query(MarketBar).count()

    assert count1 == count2, 'Duplicate ingestion should not create new rows'


# ---------------------------------------------------------------------------
# 4. Alert Deduplication Test
# ---------------------------------------------------------------------------
def test_alert_deduplication(session_factory, settings):
    """Running detection twice should produce same alert IDs"""
    from app.ingestion.mock_provider import MockProvider
    from app.ingestion.service import IngestionService
    from app.features.service import FeatureService
    from app.detection.engine import DetectionEngine

    provider = MockProvider()
    start = datetime(2025, 1, 1)
    end = datetime(2025, 4, 30)

    svc = IngestionService(session_factory, provider)
    svc.ingest(['SPIKE'], start, end)

    feat_svc = FeatureService(session_factory, settings)
    feat_svc.compute_features('SPIKE')

    engine = DetectionEngine(session_factory, settings)
    alerts1 = engine.detect('SPIKE')
    alerts2 = engine.detect('SPIKE')

    ids1 = {a.id for a in alerts1}
    ids2 = {a.id for a in alerts2}
    assert ids1 == ids2, 'Alert IDs should be deterministic'


# ---------------------------------------------------------------------------
# 5. SPIKE Ticker Anomaly Test
# ---------------------------------------------------------------------------
def test_spike_generates_high_severity(session_factory, settings):
    """SPIKE ticker's anomalous last bar should generate a high-severity alert"""
    from app.ingestion.mock_provider import MockProvider
    from app.ingestion.service import IngestionService
    from app.features.service import FeatureService
    from app.detection.engine import DetectionEngine

    provider = MockProvider()
    start = datetime(2025, 1, 1)
    end = datetime(2025, 4, 30)

    svc = IngestionService(session_factory, provider)
    svc.ingest(['SPIKE'], start, end)

    feat_svc = FeatureService(session_factory, settings)
    feat_svc.compute_features('SPIKE')

    engine = DetectionEngine(session_factory, settings)
    alerts = engine.detect('SPIKE')

    severities = {a.severity for a in alerts}
    assert 'high' in severities or 'medium' in severities, f'Expected high/medium severity, got {severities}'
