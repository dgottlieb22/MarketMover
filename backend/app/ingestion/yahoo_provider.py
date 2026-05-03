import yfinance as yf

from app.ingestion.provider import Bar, MarketDataProvider
from datetime import datetime


class YahooFinanceProvider(MarketDataProvider):
    def get_bars(
        self, ticker: str, start_time: datetime, end_time: datetime, interval: str
    ) -> list[Bar]:
        return self.get_bars_batch([ticker], start_time, end_time, interval).get(ticker, [])

    def get_bars_batch(
        self, tickers: list[str], start_time: datetime, end_time: datetime, interval: str
    ) -> dict[str, list[Bar]]:
        yf_interval = {"1d": "1d", "5m": "5m", "15m": "15m", "1h": "1h"}.get(interval, "1d")
        df = yf.download(
            " ".join(tickers),
            start=start_time.strftime("%Y-%m-%d"),
            end=end_time.strftime("%Y-%m-%d"),
            interval=yf_interval,
            progress=False,
            auto_adjust=True,
            group_by="ticker" if len(tickers) > 1 else "column",
        )
        if df.empty:
            return {t: [] for t in tickers}

        result: dict[str, list[Bar]] = {}
        for ticker in tickers:
            try:
                if len(tickers) > 1:
                    tdf = df[ticker].dropna(subset=["Close"])
                else:
                    # Single ticker: flatten MultiIndex if present
                    tdf = df
                    if hasattr(tdf.columns, "levels") and len(tdf.columns.levels) > 1:
                        tdf.columns = tdf.columns.droplevel("Ticker")
                    tdf = tdf.dropna(subset=["Close"])

                bars = []
                for ts, row in tdf.iterrows():
                    vol = int(row["Volume"]) if row["Volume"] == row["Volume"] else 0
                    if vol == 0:
                        continue
                    o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
                    bars.append(Bar(
                        ticker=ticker,
                        timestamp=ts.to_pydatetime().replace(tzinfo=None),
                        open=round(o, 4), high=round(h, 4),
                        low=round(l, 4), close=round(c, 4),
                        volume=vol, vwap=round((h + l + c) / 3, 4),
                    ))
                result[ticker] = bars
            except Exception:
                result[ticker] = []
        return result
