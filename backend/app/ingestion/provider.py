from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Bar:
    ticker: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float | None = None


class MarketDataProvider(ABC):
    @abstractmethod
    def get_bars(
        self, ticker: str, start_time: datetime, end_time: datetime, interval: str
    ) -> list[Bar]: ...

    def get_bars_batch(
        self, tickers: list[str], start_time: datetime, end_time: datetime, interval: str
    ) -> dict[str, list[Bar]]:
        """Fetch bars for multiple tickers. Default: call get_bars per ticker."""
        return {t: self.get_bars(t, start_time, end_time, interval) for t in tickers}
