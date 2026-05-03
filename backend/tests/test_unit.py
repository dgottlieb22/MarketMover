import json
import uuid
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from app.config import Settings
from app.db.models import (
    Base, IngestionRun, MarketBar, MarketFeature, MovementAlert,
)
from app.ingestion.mock_provider import MockProvider
from app.ingestion.provider import Bar, MarketDataProvider
from app.ingestion.service import IngestionService
from app.features.service import FeatureService
from app.detection.engine import DetectionEngine
from app.backtesting.service import BacktestService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def insert_bars(session, ticker, bars_data):
    """bars_data is list of (timestamp, open, high, low, close, volume)"""
    for ts, o, h, l, c, v in bars_data:
        session.merge(MarketBar(
            ticker=ticker, interval='1d', timestamp=ts,
            open=o, high=h, low=l, close=c, volume=v,
            vwap=(h + l + c) / 3, provider='test', ingested_at=datetime.now(UTC),
        ))
    session.commit()


def insert_feature(session, ticker, timestamp, **kwargs):
    defaults = dict(
        ticker=ticker, interval='1d', timestamp=timestamp,
        return_pct=0.01, gap_pct=0.005, volume_ratio=1.0,
        relative_volume=1.0, rolling_volatility_20d=0.02,
        rolling_return_mean_60d=0.001, rolling_return_std_60d=0.02,
        return_zscore_60d=0.5, volume_zscore_60d=0.5,
        gap_percentile_60d=50.0, computed_at=datetime.now(UTC),
    )
    defaults.update(kwargs)
    session.merge(MarketFeature(**defaults))
    session.commit()


class FailingProvider(MarketDataProvider):
    def __init__(self, fail_ticker='FAIL'):
        self.fail_ticker = fail_ticker

    def get_bars(self, ticker, start_time, end_time, interval):
        if ticker == self.fail_ticker:
            raise ValueError(f'Provider error for {ticker}')
        return MockProvider().get_bars(ticker, start_time, end_time, interval)


# ===========================================================================
# 1. Config tests
# ===========================================================================

class TestConfig:
    def test_default_settings(self, settings):
        assert settings.database_url == "sqlite:///./market_data.db"
        assert settings.provider == "mock"
        assert settings.rolling_window_days == 60
        assert settings.volatility_window_days == 20

    def test_settings_thresholds(self, settings):
        assert settings.price_zscore_threshold > 0
        assert settings.volume_ratio_threshold > 0
        assert settings.gap_percentile_upper > settings.gap_percentile_lower
        assert settings.severity_low < settings.severity_medium < settings.severity_high


# ===========================================================================
# 2. Model tests
# ===========================================================================

class TestModels:
    def test_create_market_bar(self, session):
        bar = MarketBar(
            ticker='TEST', interval='1d', timestamp=datetime(2024, 1, 2),
            open=100.0, high=105.0, low=99.0, close=103.0, volume=1000000,
            vwap=102.33, provider='test', ingested_at=datetime.now(UTC),
        )
        session.add(bar)
        session.commit()
        result = session.query(MarketBar).filter_by(ticker='TEST').first()
        assert result.close == 103.0

    def test_create_market_feature(self, session):
        f = MarketFeature(
            ticker='TEST', interval='1d', timestamp=datetime(2024, 1, 2),
            return_pct=0.03, gap_pct=0.01, computed_at=datetime.now(UTC),
        )
        session.add(f)
        session.commit()
        result = session.query(MarketFeature).filter_by(ticker='TEST').first()
        assert result.return_pct == pytest.approx(0.03)

    def test_create_movement_alert(self, session):
        a = MovementAlert(
            id=str(uuid.uuid4()), ticker='TEST', timestamp=datetime(2024, 1, 2),
            severity='high', signal_type='price_move', score=90.0,
            explanation='big move', metrics='{}', created_at=datetime.now(UTC),
        )
        session.add(a)
        session.commit()
        result = session.query(MovementAlert).filter_by(ticker='TEST').first()
        assert result.severity == 'high'

    def test_create_ingestion_run(self, session):
        r = IngestionRun(
            id=str(uuid.uuid4()), provider='mock', interval='1d',
            start_time=datetime(2024, 1, 1), end_time=datetime(2024, 1, 5),
            status='success', started_at=datetime.now(UTC),
        )
        session.add(r)
        session.commit()
        result = session.query(IngestionRun).first()
        assert result.status == 'success'

    def test_market_bar_composite_pk(self, session):
        ts = datetime(2024, 1, 2)
        bar1 = MarketBar(
            ticker='TEST', interval='1d', timestamp=ts,
            open=100.0, high=105.0, low=99.0, close=103.0, volume=1000000,
            vwap=102.33, provider='test', ingested_at=datetime.now(UTC),
        )
        session.merge(bar1)
        session.commit()
        # upsert with different close
        bar2 = MarketBar(
            ticker='TEST', interval='1d', timestamp=ts,
            open=100.0, high=105.0, low=99.0, close=110.0, volume=1000000,
            vwap=102.33, provider='test', ingested_at=datetime.now(UTC),
        )
        session.merge(bar2)
        session.commit()
        count = session.query(MarketBar).filter_by(ticker='TEST').count()
        assert count == 1
        result = session.query(MarketBar).filter_by(ticker='TEST').first()
        assert result.close == 110.0


# ===========================================================================
# 3. MockProvider tests
# ===========================================================================

class TestMockProvider:
    def test_mock_provider_returns_bars(self):
        p = MockProvider()
        bars = p.get_bars('AAPL', datetime(2024, 1, 1), datetime(2024, 1, 10), '1d')
        assert len(bars) > 0

    def test_mock_provider_skips_weekends(self):
        p = MockProvider()
        bars = p.get_bars('AAPL', datetime(2024, 1, 1), datetime(2024, 1, 31), '1d')
        for bar in bars:
            assert bar.timestamp.weekday() < 5

    def test_mock_provider_deterministic(self):
        p = MockProvider()
        bars1 = p.get_bars('AAPL', datetime(2024, 1, 1), datetime(2024, 1, 10), '1d')
        bars2 = p.get_bars('AAPL', datetime(2024, 1, 1), datetime(2024, 1, 10), '1d')
        assert len(bars1) == len(bars2)
        for b1, b2 in zip(bars1, bars2):
            assert b1.close == b2.close
            assert b1.volume == b2.volume

    def test_mock_provider_spike_ticker(self):
        p = MockProvider()
        bars = p.get_bars('SPIKE', datetime(2024, 1, 1), datetime(2024, 1, 10), '1d')
        last = bars[-1]
        prev = bars[-2]
        # volume should be ~10x
        assert last.volume > prev.volume * 5
        # large return
        ret = (last.close - prev.close) / prev.close
        assert abs(ret) > 0.10

    def test_mock_provider_bar_fields(self):
        p = MockProvider()
        bars = p.get_bars('AAPL', datetime(2024, 1, 1), datetime(2024, 1, 5), '1d')
        for bar in bars:
            assert bar.ticker == 'AAPL'
            assert bar.open > 0
            assert bar.high >= bar.open or bar.high >= bar.close
            assert bar.low > 0
            assert bar.close > 0
            assert bar.volume >= 0
            assert bar.vwap is not None


# ===========================================================================
# 4. IngestionService tests
# ===========================================================================

class TestIngestionService:
    def test_ingest_success(self, session_factory):
        svc = IngestionService(session_factory, MockProvider())
        run = svc.ingest(['AAPL'], datetime(2024, 1, 1), datetime(2024, 1, 10))
        assert run.status == 'success'
        s = session_factory()
        count = s.query(MarketBar).filter_by(ticker='AAPL').count()
        assert count > 0
        s.close()

    def test_ingest_idempotent(self, session_factory):
        svc = IngestionService(session_factory, MockProvider())
        svc.ingest(['AAPL'], datetime(2024, 1, 1), datetime(2024, 1, 10))
        svc.ingest(['AAPL'], datetime(2024, 1, 1), datetime(2024, 1, 10))
        s = session_factory()
        count = s.query(MarketBar).filter_by(ticker='AAPL').count()
        # MockProvider is deterministic, merge prevents duplicates
        bars = MockProvider().get_bars('AAPL', datetime(2024, 1, 1), datetime(2024, 1, 10), '1d')
        assert count == len(bars)
        s.close()

    def test_ingest_records_run(self, session_factory):
        svc = IngestionService(session_factory, MockProvider())
        run = svc.ingest(['AAPL'], datetime(2024, 1, 1), datetime(2024, 1, 10))
        assert run.provider == 'MockProvider'
        assert run.interval == '1d'
        assert run.started_at is not None
        assert run.finished_at is not None

    def test_ingest_partial_failure(self, session_factory):
        svc = IngestionService(session_factory, FailingProvider(fail_ticker='FAIL'))
        run = svc.ingest(['AAPL', 'FAIL'], datetime(2024, 1, 1), datetime(2024, 1, 10))
        assert run.status == 'partial'
        assert 'FAIL' in run.error_message


# ===========================================================================
# 5. FeatureService tests
# ===========================================================================

class TestFeatureService:
    def test_compute_features_return_pct(self, session_factory, session, settings):
        ts1, ts2 = datetime(2024, 1, 2), datetime(2024, 1, 3)
        insert_bars(session, 'TEST', [
            (ts1, 100, 105, 99, 100, 1000000),
            (ts2, 101, 106, 100, 110, 1000000),
        ])
        svc = FeatureService(session_factory, settings)
        features = svc.compute_features('TEST')
        assert len(features) == 1
        assert features[0].return_pct == pytest.approx((110 - 100) / 100)

    def test_compute_features_gap_pct(self, session_factory, session, settings):
        ts1, ts2 = datetime(2024, 1, 2), datetime(2024, 1, 3)
        insert_bars(session, 'TEST', [
            (ts1, 100, 105, 99, 100, 1000000),
            (ts2, 102, 106, 100, 105, 1000000),
        ])
        svc = FeatureService(session_factory, settings)
        features = svc.compute_features('TEST')
        assert features[0].gap_pct == pytest.approx((102 - 100) / 100)

    def test_compute_features_rolling_stats(self, session_factory, session, settings):
        base = datetime(2024, 1, 1)
        bars_data = []
        for i in range(70):
            ts = base + timedelta(days=i)
            c = 100 + i * 0.1
            bars_data.append((ts, c - 0.5, c + 0.5, c - 1, c, 1000000))
        insert_bars(session, 'TEST', bars_data)
        svc = FeatureService(session_factory, settings)
        features = svc.compute_features('TEST')
        # Features at index 60+ (i.e. bar index 61+) should have rolling stats
        late = [f for f in features if f.rolling_return_mean_60d is not None]
        assert len(late) > 0
        for f in late:
            assert f.rolling_return_std_60d is not None
            assert f.return_zscore_60d is not None

    def test_compute_features_volatility(self, session_factory, session, settings):
        base = datetime(2024, 1, 1)
        bars_data = []
        for i in range(25):
            ts = base + timedelta(days=i)
            c = 100 + i * 0.5
            bars_data.append((ts, c - 0.5, c + 0.5, c - 1, c, 1000000))
        insert_bars(session, 'TEST', bars_data)
        svc = FeatureService(session_factory, settings)
        features = svc.compute_features('TEST')
        # After index 20 in return_pcts (i.e. i+1 >= 20), volatility should be set
        has_vol = [f for f in features if f.rolling_volatility_20d is not None]
        assert len(has_vol) > 0

    def test_compute_features_zscore(self, session_factory, session, settings):
        base = datetime(2024, 1, 1)
        bars_data = []
        for i in range(65):
            ts = base + timedelta(days=i)
            c = 100 + i * 0.1
            bars_data.append((ts, c - 0.5, c + 0.5, c - 1, c, 1000000))
        insert_bars(session, 'TEST', bars_data)
        svc = FeatureService(session_factory, settings)
        features = svc.compute_features('TEST')
        f = [x for x in features if x.return_zscore_60d is not None][-1]
        # Verify zscore = (return - mean) / std
        assert f.rolling_return_std_60d > 0
        expected = (f.return_pct - f.rolling_return_mean_60d) / f.rolling_return_std_60d
        assert f.return_zscore_60d == pytest.approx(expected, rel=1e-6)

    def test_compute_features_volume_zscore(self, session_factory, session, settings):
        base = datetime(2024, 1, 1)
        bars_data = []
        for i in range(65):
            ts = base + timedelta(days=i)
            c = 100 + i * 0.1
            bars_data.append((ts, c - 0.5, c + 0.5, c - 1, c, 1000000 + i * 1000))
        insert_bars(session, 'TEST', bars_data)
        svc = FeatureService(session_factory, settings)
        features = svc.compute_features('TEST')
        f = [x for x in features if x.volume_zscore_60d is not None][-1]
        assert f.volume_zscore_60d is not None

    def test_compute_features_gap_percentile(self, session_factory, session, settings):
        base = datetime(2024, 1, 1)
        bars_data = []
        for i in range(65):
            ts = base + timedelta(days=i)
            c = 100 + i * 0.1
            bars_data.append((ts, c + 0.05, c + 0.5, c - 1, c, 1000000))
        insert_bars(session, 'TEST', bars_data)
        svc = FeatureService(session_factory, settings)
        features = svc.compute_features('TEST')
        f = [x for x in features if x.gap_percentile_60d is not None][-1]
        assert 0 <= f.gap_percentile_60d <= 100

    def test_compute_features_insufficient_data(self, session_factory, session, settings):
        insert_bars(session, 'TEST', [
            (datetime(2024, 1, 2), 100, 105, 99, 100, 1000000),
        ])
        svc = FeatureService(session_factory, settings)
        features = svc.compute_features('TEST')
        assert features == []


# ===========================================================================
# 6. DetectionEngine tests
# ===========================================================================

class TestDetectionEngine:
    def test_detect_price_move(self, session_factory, session, settings):
        # Need score >= 50. Boost return_zscore and volume_zscore to raise score.
        insert_feature(session, 'TEST', datetime(2024, 1, 2),
                       return_zscore_60d=3.0, return_pct=0.05,
                       volume_zscore_60d=3.0, relative_volume=3.0,
                       rolling_volatility_20d=0.04)
        engine = DetectionEngine(session_factory, settings)
        alerts = engine.detect('TEST')
        types = [a.signal_type for a in alerts]
        assert 'price_move' in types

    def test_detect_volume_spike(self, session_factory, session, settings):
        insert_feature(session, 'TEST', datetime(2024, 1, 2),
                       relative_volume=4.0, volume_zscore_60d=4.0,
                       return_zscore_60d=2.0, rolling_volatility_20d=0.04)
        engine = DetectionEngine(session_factory, settings)
        alerts = engine.detect('TEST')
        types = [a.signal_type for a in alerts]
        assert 'volume_spike' in types

    def test_detect_gap(self, session_factory, session, settings):
        insert_feature(session, 'TEST', datetime(2024, 1, 2),
                       gap_percentile_60d=98.0,
                       return_zscore_60d=2.0, volume_zscore_60d=2.0,
                       rolling_volatility_20d=0.04)
        engine = DetectionEngine(session_factory, settings)
        alerts = engine.detect('TEST')
        types = [a.signal_type for a in alerts]
        assert 'gap' in types

    def test_detect_combined(self, session_factory, session, settings):
        insert_feature(session, 'TEST', datetime(2024, 1, 2),
                       return_zscore_60d=2.5, relative_volume=3.0,
                       volume_zscore_60d=3.0, rolling_volatility_20d=0.04)
        engine = DetectionEngine(session_factory, settings)
        alerts = engine.detect('TEST')
        types = [a.signal_type for a in alerts]
        assert 'combined' in types

    def test_detect_no_alert_below_threshold(self, session_factory, session, settings):
        insert_feature(session, 'TEST', datetime(2024, 1, 2),
                       return_zscore_60d=0.5, volume_zscore_60d=0.5,
                       relative_volume=1.0, gap_percentile_60d=50.0,
                       rolling_volatility_20d=0.01)
        engine = DetectionEngine(session_factory, settings)
        alerts = engine.detect('TEST')
        assert len(alerts) == 0

    def test_detect_deduplication(self, session_factory, session, settings):
        insert_feature(session, 'TEST', datetime(2024, 1, 2),
                       return_zscore_60d=3.0, return_pct=0.05)
        engine = DetectionEngine(session_factory, settings)
        alerts1 = engine.detect('TEST')
        alerts2 = engine.detect('TEST')
        ids1 = {a.id for a in alerts1}
        ids2 = {a.id for a in alerts2}
        assert ids1 == ids2

    def test_score_computation(self, session_factory, session, settings):
        insert_feature(session, 'TEST', datetime(2024, 1, 2),
                       return_zscore_60d=3.0, volume_zscore_60d=2.0,
                       gap_percentile_60d=80.0, rolling_volatility_20d=0.03,
                       return_pct=0.05, relative_volume=3.0)
        engine = DetectionEngine(session_factory, settings)
        alerts = engine.detect('TEST')
        assert len(alerts) > 0
        # Manually compute expected score
        nr = min(3.0 / 5.0 * 100, 100)  # 60
        nv = min(2.0 / 5.0 * 100, 100)  # 40
        ng = 80.0
        nvol = min(0.03 / 0.05 * 100, 100)  # 60
        expected = 0.40 * nr + 0.35 * nv + 0.15 * ng + 0.10 * nvol
        assert alerts[0].score == pytest.approx(expected, abs=0.01)

    def test_severity_levels(self, settings):
        engine = DetectionEngine.__new__(DetectionEngine)
        engine.settings = settings
        assert engine._get_severity(90) == 'high'
        assert engine._get_severity(85) == 'high'
        assert engine._get_severity(75) == 'medium'
        assert engine._get_severity(70) == 'medium'
        assert engine._get_severity(55) == 'low'
        assert engine._get_severity(50) == 'low'
        assert engine._get_severity(40) is None

    def test_explanation_generation(self, session_factory, session, settings):
        insert_feature(session, 'AAPL', datetime(2024, 1, 2),
                       return_zscore_60d=3.0, return_pct=0.05,
                       volume_zscore_60d=3.0, relative_volume=3.0,
                       rolling_volatility_20d=0.04)
        engine = DetectionEngine(session_factory, settings)
        alerts = engine.detect('AAPL')
        assert len(alerts) > 0
        assert 'AAPL' in alerts[0].explanation
        assert 'up' in alerts[0].explanation


# ===========================================================================
# 7. BacktestService tests
# ===========================================================================

class TestBacktestService:
    def test_backtest_empty(self, session_factory):
        svc = BacktestService(session_factory)
        result = svc.run('2024-01-01', '2024-01-31')
        assert result.total_alerts == 0

    def test_backtest_counts(self, session_factory, session):
        for i, (sev, sig) in enumerate([
            ('high', 'price_move'), ('medium', 'volume_spike'), ('low', 'gap'),
        ]):
            session.add(MovementAlert(
                id=str(uuid.uuid4()), ticker='TEST', timestamp=datetime(2024, 1, 2 + i),
                severity=sev, signal_type=sig, score=90 - i * 10,
                explanation='test', metrics='{}', created_at=datetime.now(UTC),
            ))
        session.commit()
        svc = BacktestService(session_factory)
        result = svc.run('2024-01-01', '2024-01-31')
        assert result.total_alerts == 3
        assert result.alerts_by_severity['high'] == 1
        assert result.alerts_by_signal_type['price_move'] == 1

    def test_backtest_top_alerts(self, session_factory, session):
        for i in range(5):
            session.add(MovementAlert(
                id=str(uuid.uuid4()), ticker='TEST', timestamp=datetime(2024, 1, 2 + i),
                severity='high', signal_type='price_move', score=50 + i * 10,
                explanation='test', metrics='{}', created_at=datetime.now(UTC),
            ))
        session.commit()
        svc = BacktestService(session_factory)
        result = svc.run('2024-01-01', '2024-01-31')
        scores = [a['score'] for a in result.top_alerts]
        assert scores == sorted(scores, reverse=True)


# ===========================================================================
# 8. Explanation tests
# ===========================================================================

class TestExplanation:
    def _make_engine(self, settings):
        engine = DetectionEngine.__new__(DetectionEngine)
        engine.settings = settings
        return engine

    def _make_feature(self, **kwargs):
        defaults = dict(
            ticker='TEST', interval='1d', timestamp=datetime(2024, 1, 2),
            return_pct=0.01, gap_pct=0.005, volume_ratio=1.0,
            relative_volume=1.0, rolling_volatility_20d=0.02,
            rolling_return_mean_60d=0.001, rolling_return_std_60d=0.02,
            return_zscore_60d=0.5, volume_zscore_60d=0.5,
            gap_percentile_60d=50.0, computed_at=datetime.now(UTC),
        )
        defaults.update(kwargs)
        return MarketFeature(**defaults)

    def test_explanation_up_move(self, settings):
        engine = self._make_engine(settings)
        f = self._make_feature(return_pct=0.05)
        explanation = engine._generate_explanation(f, 'price_move')
        assert 'up' in explanation

    def test_explanation_down_move(self, settings):
        engine = self._make_engine(settings)
        f = self._make_feature(return_pct=-0.05)
        explanation = engine._generate_explanation(f, 'price_move')
        assert 'down' in explanation

    def test_explanation_volume_context(self, settings):
        engine = self._make_engine(settings)
        f = self._make_feature(relative_volume=2.0)
        explanation = engine._generate_explanation(f, 'volume_spike')
        assert 'olume' in explanation  # Volume or volume

    def test_explanation_gap_context(self, settings):
        engine = self._make_engine(settings)
        f = self._make_feature(gap_percentile_60d=95.0)
        explanation = engine._generate_explanation(f, 'gap')
        assert 'gap' in explanation
