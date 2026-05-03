"""CLI for running the market movement detection pipeline."""

import argparse
import sys
from datetime import datetime, timedelta

from app.config import get_settings
from app.db.session import get_engine, get_session_factory, init_db
from app.detection.engine import DetectionEngine
from app.features.service import FeatureService
from app.ingestion.service import IngestionService


DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "AMD", "NFLX", "INTC"]


def get_provider(name: str):
    if name == "yahoo":
        from app.ingestion.yahoo_provider import YahooFinanceProvider
        return YahooFinanceProvider()
    from app.ingestion.mock_provider import MockProvider
    return MockProvider()


def cmd_run(args):
    """Run the full pipeline: ingest -> features -> detect."""
    settings = get_settings()
    engine = get_engine(settings.database_url)
    init_db(engine)
    factory = get_session_factory(engine)

    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    provider = get_provider(args.provider)
    end = datetime.now()
    start = end - timedelta(days=args.days)

    print(f"Provider: {args.provider}")
    print(f"Tickers:  {', '.join(tickers)}")
    print(f"Range:    {start.date()} to {end.date()} ({args.days} days)")
    print()

    # Ingest
    print("Ingesting bars...")
    svc = IngestionService(factory, provider)
    run = svc.ingest(tickers, start, end, interval=args.interval)
    print(f"  Status: {run.status}")
    if run.error_message:
        print(f"  Errors: {run.error_message}")

    # Features
    print("Computing features...")
    feat_svc = FeatureService(factory, settings)
    for t in tickers:
        feat_svc.compute_features(t, args.interval)
    print("  Done.")

    # Detect
    print("Running detection...")
    det = DetectionEngine(factory, settings)
    all_alerts = []
    for t in tickers:
        alerts = det.detect(t, args.interval)
        all_alerts.extend(alerts)

    if not all_alerts:
        print("  No anomalies detected.")
        return

    # Print alerts
    all_alerts.sort(key=lambda a: a.score, reverse=True)
    print(f"\n{'='*70}")
    print(f"  {len(all_alerts)} alert(s) detected")
    print(f"{'='*70}\n")

    for a in all_alerts[:20]:
        print(f"[{a.severity.upper():6s}] {a.ticker}  score={a.score:.1f}  type={a.signal_type}")
        print(f"         {a.explanation}")
        print()


def cmd_alerts(args):
    """Show stored alerts."""
    settings = get_settings()
    engine = get_engine(settings.database_url)
    factory = get_session_factory(engine)

    from app.db.models import MovementAlert
    with factory() as session:
        q = session.query(MovementAlert).order_by(MovementAlert.score.desc())
        if args.severity:
            q = q.filter(MovementAlert.severity == args.severity)
        alerts = q.limit(args.limit).all()

    if not alerts:
        print("No alerts found.")
        return

    for a in alerts:
        print(f"[{a.severity.upper():6s}] {a.ticker}  score={a.score:.1f}  type={a.signal_type}  date={a.timestamp.date()}")
        print(f"         {a.explanation}")
        print()


def main():
    parser = argparse.ArgumentParser(prog="mmd", description="Market Movement Detector")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run the full pipeline")
    run_p.add_argument("-t", "--tickers", default=",".join(DEFAULT_TICKERS), help="Comma-separated tickers")
    run_p.add_argument("-p", "--provider", default="yahoo", choices=["yahoo", "mock"], help="Data provider")
    run_p.add_argument("-d", "--days", type=int, default=120, help="Days of history to fetch")
    run_p.add_argument("-i", "--interval", default="1d", help="Bar interval")

    alerts_p = sub.add_parser("alerts", help="Show stored alerts")
    alerts_p.add_argument("-s", "--severity", choices=["high", "medium", "low"])
    alerts_p.add_argument("-l", "--limit", type=int, default=20)

    args = parser.parse_args()
    if args.command == "run":
        cmd_run(args)
    elif args.command == "alerts":
        cmd_alerts(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
