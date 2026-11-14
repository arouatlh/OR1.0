from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    http_host: str = "0.0.0.0"
    http_port: int = 8998
    db_path: str = "./data/astrovitals.db"
    cors_origins: str = "*"

    alert_sustain_samples: int = 3
    alert_resolve_samples: int = 5
    sim_interval_ms: int = 1000

    ml_enabled: bool = True
    ml_window_samples: int = 30
    ml_every_n_samples: int = 5
    ml_timeout_ms: int = 500
    ml_alert_threshold: float = 0.8

    sync_remote_url: str = ""
    api_key: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        if not self.cors_origins or self.cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
