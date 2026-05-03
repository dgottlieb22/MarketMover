"""Tests for YahooFinanceProvider and CLI."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.ingestion.provider import Bar
from app.ingestion.yahoo_provider import YahooFinanceProvider


# ---------------------------------------------------------------------------
# YahooFinanceProvider tests (mocked — no real network calls)
# ---------------------------------------------------------------------------

class TestYahooFinanceProvider:
    def _make_df(self, rows):
        """Build a DataFrame mimicking yfinance output."""
        idx = pd.DatetimeIndex([r[0] for r in rows])
        data = {
            "Open": [r[1] for r in rows],
            "High": [r[2] for r in rows],
            "Low": [r[3] for r in rows],
            "Close": [r[4] for r in rows],
            "Volume": [r[5] for r in rows],
        }
        return pd.DataFrame(data, index=idx)

    @patch("app.ingestion.yahoo_provider.yf.download")
    def test_returns_bars(self, mock_dl):
        mock_dl.return_value = self._make_df([
            ("2025-03-10", 100.0, 105.0, 99.0, 103.0, 5_000_000),
            ("2025-03-11", 103.0, 107.0, 102.0, 106.0, 6_000_000),
        ])
        provider = YahooFinanceProvider()
        bars = provider.get_bars("AAPL", datetime(2025, 3, 10), datetime(2025, 3, 12), "1d")

        assert len(bars) == 2
        assert all(isinstance(b, Bar) for b in bars)
        assert bars[0].ticker == "AAPL"
        assert bars[0].close == 103.0
        assert bars[1].volume == 6_000_000

    @patch("app.ingestion.yahoo_provider.yf.download")
    def test_empty_df(self, mock_dl):
        mock_dl.return_value = pd.DataFrame()
        provider = YahooFinanceProvider()
        bars = provider.get_bars("FAKE", datetime(2025, 1, 1), datetime(2025, 1, 2), "1d")
        assert bars == []

    @patch("app.ingestion.yahoo_provider.yf.download")
    def test_skips_zero_volume(self, mock_dl):
        mock_dl.return_value = self._make_df([
            ("2025-03-10", 100.0, 105.0, 99.0, 103.0, 0),
            ("2025-03-11", 103.0, 107.0, 102.0, 106.0, 5_000_000),
        ])
        provider = YahooFinanceProvider()
        bars = provider.get_bars("TEST", datetime(2025, 3, 10), datetime(2025, 3, 12), "1d")
        assert len(bars) == 1
        assert bars[0].volume == 5_000_000

    @patch("app.ingestion.yahoo_provider.yf.download")
    def test_vwap_approximation(self, mock_dl):
        mock_dl.return_value = self._make_df([
            ("2025-03-10", 100.0, 110.0, 90.0, 105.0, 1_000_000),
        ])
        provider = YahooFinanceProvider()
        bars = provider.get_bars("TEST", datetime(2025, 3, 10), datetime(2025, 3, 11), "1d")
        expected_vwap = round((110.0 + 90.0 + 105.0) / 3, 4)
        assert bars[0].vwap == expected_vwap

    @patch("app.ingestion.yahoo_provider.yf.download")
    def test_multiindex_columns(self, mock_dl):
        """yfinance sometimes returns MultiIndex columns; provider should handle it."""
        idx = pd.DatetimeIndex(["2025-03-10"])
        arrays = [["Open", "High", "Low", "Close", "Volume"], ["AAPL"] * 5]
        cols = pd.MultiIndex.from_arrays(arrays, names=["Price", "Ticker"])
        df = pd.DataFrame([[100.0, 105.0, 99.0, 103.0, 5_000_000]], index=idx, columns=cols)
        mock_dl.return_value = df

        provider = YahooFinanceProvider()
        bars = provider.get_bars("AAPL", datetime(2025, 3, 10), datetime(2025, 3, 11), "1d")
        assert len(bars) == 1
        assert bars[0].close == 103.0


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLI:
    def test_cmd_run_with_mock(self, session_factory, capsys):
        """CLI run command works end-to-end with mock provider."""
        from argparse import Namespace
        from app.cli import cmd_run
        from app.db.models import Base

        args = Namespace(
            tickers="AAPL,SPIKE",
            provider="mock",
            days=120,
            interval="1d",
        )

        # Patch get_settings to use in-memory DB
        with patch("app.cli.get_settings") as mock_settings, \
             patch("app.cli.get_engine") as mock_engine, \
             patch("app.cli.get_session_factory") as mock_factory, \
             patch("app.cli.init_db"):
            from app.config import Settings
            mock_settings.return_value = Settings()
            mock_engine.return_value = session_factory.kw["bind"]
            mock_factory.return_value = session_factory

            cmd_run(args)

        captured = capsys.readouterr()
        assert "Ingesting bars..." in captured.out
        assert "Computing features..." in captured.out
        assert "Running detection..." in captured.out

    def test_main_no_args(self):
        """CLI with no args prints help and exits."""
        from app.cli import main
        with patch("sys.argv", ["mmd"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
