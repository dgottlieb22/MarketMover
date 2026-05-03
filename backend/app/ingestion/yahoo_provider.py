import yfinance as yf

from app.ingestion.provider import Bar, MarketDataProvider
from datetime import datetime


class YahooFinanceProvider(MarketDataProvider):
    def get_bars(
        self, ticker: str, start_time: datetime, end_time: datetime, interval: str
    ) -> list[Bar]:
        yf_interval = {"1d": "1d", "5m": "5m", "15m": "15m", "1h": "1h"}.get(
            interval, "1d"
        )
        df = yf.download(
            ticker,
            start=start_time.strftime("%Y-%m-%d"),
            end=end_time.strftime("%Y-%m-%d"),
            interval=yf_interval,
            progress=False,
            auto_adjust=True,
        )
        if df.empty:
            return []

        # yfinance may return MultiIndex columns for single ticker; flatten
        if hasattr(df.columns, "levels") and len(df.columns.levels) > 1:
            df.columns = df.columns.droplevel("Ticker")

        bars = []
        for ts, row in df.iterrows():
            vol = int(row["Volume"]) if row["Volume"] == row["Volume"] else 0
            if vol == 0:
                continue
            o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
            bars.append(Bar(
                ticker=ticker,
                timestamp=ts.to_pydatetime().replace(tzinfo=None),
                open=round(o, 4),
                high=round(h, 4),
                low=round(l, 4),
                close=round(c, 4),
                volume=vol,
                vwap=round((h + l + c) / 3, 4),
            ))
        return bars
