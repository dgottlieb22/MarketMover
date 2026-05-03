import hashlib
import random
from datetime import datetime, timedelta

from app.ingestion.provider import Bar, MarketDataProvider


class MockProvider(MarketDataProvider):
    def get_bars(
        self, ticker: str, start_time: datetime, end_time: datetime, interval: str
    ) -> list[Bar]:
        seed = int(hashlib.md5(ticker.encode()).hexdigest(), 16) % (2**31)
        rng = random.Random(seed)

        bars: list[Bar] = []
        price = 50.0
        day = start_time

        while day <= end_time:
            if day.weekday() >= 5:
                day += timedelta(days=1)
                continue

            is_last = (day + timedelta(days=1)) > end_time or (
                day.weekday() == 4
                and (day + timedelta(days=3)) > end_time
            )

            ret = rng.gauss(0, 0.02)
            vol = int(rng.gauss(1_000_000, 100_000))

            if ticker == "SPIKE" and is_last:
                ret = 0.15
                vol *= 10

            price *= 1 + ret
            o = price / (1 + ret)
            h = max(o, price) * (1 + abs(rng.gauss(0, 0.005)))
            l = min(o, price) * (1 - abs(rng.gauss(0, 0.005)))
            c = price
            vwap = (h + l + c) / 3

            bars.append(Bar(
                ticker=ticker, timestamp=day,
                open=round(o, 4), high=round(h, 4),
                low=round(l, 4), close=round(c, 4),
                volume=max(vol, 0), vwap=round(vwap, 4),
            ))
            day += timedelta(days=1)

        return bars
