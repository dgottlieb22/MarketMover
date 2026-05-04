"""Purge market data older than the retention window."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import sessionmaker

from app.db.models import IngestionRun, MarketBar, MarketFeature, MovementAlert


def purge_old_data(session_factory: sessionmaker, retention_days: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    # Use naive cutoff for SQLite compatibility
    cutoff_naive = cutoff.replace(tzinfo=None)
    deleted = 0
    with session_factory() as session:
        for model, col in [
            (MovementAlert, MovementAlert.timestamp),
            (MarketFeature, MarketFeature.timestamp),
            (MarketBar, MarketBar.timestamp),
            (IngestionRun, IngestionRun.started_at),
        ]:
            n = session.query(model).filter(col < cutoff_naive).delete(synchronize_session=False)
            deleted += n
        session.commit()
    return deleted
