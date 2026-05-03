import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.config import Settings, get_settings
from app.db.models import MarketFeature, MovementAlert


class DetectionEngine:
    def __init__(self, session_factory, settings: Settings | None = None):
        self.session_factory = session_factory
        self.settings = settings or get_settings()

    def detect(self, ticker: str, interval: str = "1d") -> list[MovementAlert]:
        s = self.settings
        alerts: list[MovementAlert] = []

        with self.session_factory() as session:
            stmt = (
                select(MarketFeature)
                .where(MarketFeature.ticker == ticker, MarketFeature.interval == interval)
                .order_by(MarketFeature.timestamp)
            )
            features = session.execute(stmt).scalars().all()

            for feature in features:
                signals = self._check_signals(feature)
                for signal_type in signals:
                    score = self._compute_score(feature)
                    severity = self._get_severity(score)
                    if severity is None:
                        continue

                    explanation = self._generate_explanation(feature, signal_type)
                    dedup_key = f"{ticker}:{signal_type}:{feature.timestamp.date()}"
                    alert_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, dedup_key))

                    alert = MovementAlert(
                        id=alert_id,
                        ticker=ticker,
                        timestamp=feature.timestamp,
                        severity=severity,
                        signal_type=signal_type,
                        score=round(score, 2),
                        explanation=explanation,
                        metrics=json.dumps({
                            "return_pct": feature.return_pct,
                            "return_zscore_60d": feature.return_zscore_60d,
                            "relative_volume": feature.relative_volume,
                            "volume_zscore_60d": feature.volume_zscore_60d,
                            "gap_percentile_60d": feature.gap_percentile_60d,
                            "rolling_volatility_20d": feature.rolling_volatility_20d,
                        }),
                        created_at=datetime.now(UTC),
                    )
                    session.merge(alert)
                    alerts.append(alert)

            session.commit()

        return alerts

    def _check_signals(self, f: MarketFeature) -> list[str]:
        s = self.settings
        signals = []
        rz = abs(f.return_zscore_60d or 0)
        rv = f.relative_volume or 0
        vz = abs(f.volume_zscore_60d or 0)
        gp = f.gap_percentile_60d

        if rz >= s.price_zscore_threshold:
            signals.append("price_move")
        if rv >= s.volume_ratio_threshold or vz >= s.volume_zscore_threshold:
            signals.append("volume_spike")
        if gp is not None and (gp >= s.gap_percentile_upper or gp <= s.gap_percentile_lower):
            signals.append("gap")
        if rz >= s.combined_zscore_threshold and rv >= s.combined_volume_threshold:
            signals.append("combined")

        return signals

    def _compute_score(self, feature: MarketFeature) -> float:
        s = self.settings
        nr = min(abs(feature.return_zscore_60d or 0) / 5.0 * 100, 100)
        nv = min(abs(feature.volume_zscore_60d or 0) / 5.0 * 100, 100)
        ng = feature.gap_percentile_60d if feature.gap_percentile_60d is not None else 0
        nvol = min((feature.rolling_volatility_20d or 0) / 0.05 * 100, 100)
        return s.score_weight_return * nr + s.score_weight_volume * nv + s.score_weight_gap * ng + s.score_weight_volatility * nvol

    def _get_severity(self, score: float) -> str | None:
        s = self.settings
        if score >= s.severity_high:
            return "high"
        if score >= s.severity_medium:
            return "medium"
        if score >= s.severity_low:
            return "low"
        return None

    def _generate_explanation(self, feature: MarketFeature, signal_type: str) -> str:
        parts = []
        if feature.return_pct is not None:
            direction = "up" if feature.return_pct >= 0 else "down"
            parts.append(f"{feature.ticker} is {direction} {abs(feature.return_pct * 100):.1f}%")
            if feature.return_zscore_60d is not None:
                above_below = "above" if feature.return_zscore_60d >= 0 else "below"
                parts.append(f"which is {abs(feature.return_zscore_60d):.1f} standard deviations {above_below} its 60-day average return")
        if feature.relative_volume is not None and feature.relative_volume > 1.5:
            parts.append(f"Volume is {feature.relative_volume:.1f}x its normal level")
        if feature.gap_percentile_60d is not None and (feature.gap_percentile_60d >= 90 or feature.gap_percentile_60d <= 10):
            parts.append(f"today's opening gap was larger than {feature.gap_percentile_60d:.0f}% of gaps over the last 60 trading days")
        return ". ".join(parts) + "." if parts else f"{feature.ticker} shows unusual activity."
