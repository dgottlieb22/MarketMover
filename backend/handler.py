"""
Lambda handler for the scheduled market movement detection pipeline.

Triggered by EventBridge on weekdays after market close.
Runs: ingest -> compute features -> detect anomalies -> publish alerts to SNS.
"""

import json
import os
from datetime import datetime, timedelta

import boto3

DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "AMD", "NFLX", "INTC"]


def get_db_url() -> str:
    """Resolve database URL from Secrets Manager."""
    secret_arn = os.environ.get("DB_SECRET_ARN", "")
    if not secret_arn:
        return "sqlite:///./market_data.db"

    client = boto3.client("secretsmanager")
    resp = client.get_secret_value(SecretId=secret_arn)
    secret = json.loads(resp["SecretString"])
    return (
        f"postgresql://{secret['username']}:{secret['password']}"
        f"@{secret['host']}:{secret['port']}/{secret['dbname']}"
    )


def publish_alerts(alerts: list, topic_arn: str) -> None:
    """Publish high-severity alerts to SNS."""
    if not topic_arn or not alerts:
        return

    sns = boto3.client("sns")
    high = [a for a in alerts if a.severity == "high"]
    if not high:
        return

    lines = [f"[{a.severity.upper()}] {a.ticker} (score={a.score:.1f}): {a.explanation}" for a in high]
    message = f"Market Movement Detector — {len(high)} high-severity alert(s)\n\n" + "\n\n".join(lines)

    sns.publish(
        TopicArn=topic_arn,
        Subject=f"MMD: {len(high)} high-severity alert(s) detected",
        Message=message,
    )


def main(event=None, context=None):
    """Lambda entry point."""
    from app.config import get_settings
    from app.db.models import Base
    from app.db.session import get_engine, get_session_factory
    from app.detection.engine import DetectionEngine
    from app.features.service import FeatureService
    from app.ingestion.service import IngestionService
    from app.ingestion.yahoo_provider import YahooFinanceProvider

    settings = get_settings()
    db_url = get_db_url()
    engine = get_engine(db_url)
    Base.metadata.create_all(engine)
    factory = get_session_factory(engine)

    tickers = DEFAULT_TICKERS
    end = datetime.now()
    start = end - timedelta(days=120)

    # Ingest
    provider = YahooFinanceProvider()
    svc = IngestionService(factory, provider)
    run = svc.ingest(tickers, start, end)

    # Features + Detection
    feat_svc = FeatureService(factory, settings)
    det = DetectionEngine(factory, settings)
    all_alerts = []
    for t in tickers:
        feat_svc.compute_features(t)
        all_alerts.extend(det.detect(t))

    # Publish to SNS
    topic_arn = os.environ.get("ALERT_TOPIC_ARN", "")
    publish_alerts(all_alerts, topic_arn)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "ingestion_status": run.status,
            "total_alerts": len(all_alerts),
            "high_severity": len([a for a in all_alerts if a.severity == "high"]),
        }),
    }
