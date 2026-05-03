from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import MovementAlert


@dataclass
class BacktestResult:
    start_date: str
    end_date: str
    total_alerts: int
    alerts_by_severity: dict[str, int] = field(default_factory=dict)
    alerts_by_signal_type: dict[str, int] = field(default_factory=dict)
    alerts_per_day: float = 0.0
    top_alerts: list[dict] = field(default_factory=list)


class BacktestService:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def run(self, start_date: str, end_date: str) -> BacktestResult:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

        session: Session = self.session_factory()
        alerts = (
            session.query(MovementAlert)
            .filter(MovementAlert.timestamp >= start, MovementAlert.timestamp <= end)
            .all()
        )

        total = len(alerts)
        severity_counts = Counter(a.severity for a in alerts)
        signal_counts = Counter(a.signal_type for a in alerts)
        trading_days = len({a.timestamp.date() for a in alerts}) or 1
        top = sorted(alerts, key=lambda a: a.score, reverse=True)[:10]

        return BacktestResult(
            start_date=start_date,
            end_date=end_date,
            total_alerts=total,
            alerts_by_severity=dict(severity_counts),
            alerts_by_signal_type=dict(signal_counts),
            alerts_per_day=round(total / trading_days, 2),
            top_alerts=[
                {
                    "ticker": a.ticker,
                    "timestamp": a.timestamp.isoformat(),
                    "severity": a.severity,
                    "signal_type": a.signal_type,
                    "score": a.score,
                    "explanation": a.explanation,
                }
                for a in top
            ],
        )
