from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./market_data.db"
    provider: str = "mock"
    universe_min_market_cap: float = 100_000_000
    universe_max_market_cap: float = 10_000_000_000
    universe_min_avg_dollar_volume: float = 1_000_000
    rolling_window_days: int = 60
    volatility_window_days: int = 20
    price_zscore_threshold: float = 2.5
    volume_ratio_threshold: float = 3.0
    volume_zscore_threshold: float = 3.0
    gap_percentile_upper: float = 95.0
    gap_percentile_lower: float = 5.0
    combined_zscore_threshold: float = 2.0
    combined_volume_threshold: float = 2.0
    score_weight_return: float = 0.40
    score_weight_volume: float = 0.35
    score_weight_gap: float = 0.15
    score_weight_volatility: float = 0.10
    severity_low: float = 50.0
    severity_medium: float = 70.0
    severity_high: float = 85.0

    model_config = {"env_prefix": "MMD_"}


def get_settings() -> Settings:
    return Settings()
