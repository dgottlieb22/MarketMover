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
