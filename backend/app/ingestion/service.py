import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import sessionmaker

from app.db.models import IngestionRun, MarketBar
from app.ingestion.provider import MarketDataProvider


class IngestionService:
    def __init__(self, session_factory: sessionmaker, provider: MarketDataProvider):
        self.session_factory = session_factory
        self.provider = provider

    def ingest(
        self,
        tickers: list[str],
        start_time: datetime,
        end_time: datetime,
        interval: str = "1d",
    ) -> IngestionRun:
        session = self.session_factory()
        provider_name = type(self.provider).__name__

        run = IngestionRun(
            id=str(uuid.uuid4()),
            provider=provider_name,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            status="running",
            started_at=datetime.now(UTC),
        )
        session.add(run)
        session.commit()

        errors: list[str] = []
        for ticker in tickers:
            try:
                bars = self.provider.get_bars(ticker, start_time, end_time, interval)
                now = datetime.now(UTC)
                for bar in bars:
                    session.merge(MarketBar(
                        ticker=bar.ticker,
                        interval=interval,
                        timestamp=bar.timestamp,
                        open=bar.open,
                        high=bar.high,
                        low=bar.low,
                        close=bar.close,
                        volume=bar.volume,
                        vwap=bar.vwap,
                        provider=provider_name,
                        ingested_at=now,
                    ))
                session.commit()
            except Exception as exc:
                session.rollback()
                errors.append(f"{ticker}: {exc}")

        if not errors:
            run.status = "success"
        elif len(errors) < len(tickers):
            run.status = "partial"
        else:
            run.status = "failed"

        run.error_message = "; ".join(errors) if errors else None
        run.finished_at = datetime.now(UTC)
        session.commit()
        session.close()
        return run
