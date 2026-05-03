from datetime import UTC, datetime

import numpy as np
from sqlalchemy import select

from app.config import Settings, get_settings
from app.db.models import MarketBar, MarketFeature


class FeatureService:
    def __init__(self, session_factory, settings: Settings | None = None):
        self.session_factory = session_factory
        self.settings = settings or get_settings()

    def compute_features(self, ticker: str, interval: str = "1d") -> list[MarketFeature]:
        window = self.settings.rolling_window_days
        vol_window = self.settings.volatility_window_days

        with self.session_factory() as session:
            bars = session.execute(
                select(MarketBar)
                .where(MarketBar.ticker == ticker, MarketBar.interval == interval)
                .order_by(MarketBar.timestamp)
            ).scalars().all()

            if len(bars) < 2:
                return []

            closes = np.array([b.close for b in bars])
            opens = np.array([b.open for b in bars])
            volumes = np.array([b.volume for b in bars], dtype=float)

            return_pcts = (closes[1:] - closes[:-1]) / closes[:-1]
            gap_pcts = (opens[1:] - closes[:-1]) / closes[:-1]

            now = datetime.now(UTC)
            features = []

            for i in range(len(return_pcts)):
                bar = bars[i + 1]
                f = MarketFeature(
                    ticker=ticker,
                    interval=interval,
                    timestamp=bar.timestamp,
                    return_pct=float(return_pcts[i]),
                    gap_pct=float(gap_pcts[i]),
                    computed_at=now,
                )

                idx = i + 1  # index into bars/volumes arrays
                if i + 1 >= window:
                    ret_slice = return_pcts[i + 1 - window : i + 1]
                    mean_r = float(np.mean(ret_slice))
                    std_r = float(np.std(ret_slice))
                    f.rolling_return_mean_60d = mean_r
                    f.rolling_return_std_60d = std_r
                    f.return_zscore_60d = float((return_pcts[i] - mean_r) / std_r) if std_r > 0 else None

                    vol_slice = volumes[idx + 1 - window : idx + 1]
                    mean_v = float(np.mean(vol_slice))
                    std_v = float(np.std(vol_slice))
                    f.volume_zscore_60d = float((volumes[idx] - mean_v) / std_v) if std_v > 0 else None
                    f.volume_ratio = float(volumes[idx] / mean_v) if mean_v > 0 else None
                    f.relative_volume = f.volume_ratio

                    gap_slice = gap_pcts[i + 1 - window : i + 1]
                    cur_gap = gap_pcts[i]
                    f.gap_percentile_60d = float(np.sum(gap_slice <= cur_gap) / len(gap_slice) * 100)

                if i + 1 >= vol_window:
                    ret_vol_slice = return_pcts[i + 1 - vol_window : i + 1]
                    f.rolling_volatility_20d = float(np.std(ret_vol_slice))

                features.append(session.merge(f))

            session.commit()
            return features
