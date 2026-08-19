import os
from dataclasses import dataclass, field
from pathlib import Path


def _read_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _read_path(name: str, default: str) -> Path:
    value = os.getenv(name, default).strip() or default
    return Path(value).expanduser()


@dataclass(frozen=True)
class Settings:
    app_name: str = field(
        default_factory=lambda: os.getenv("APP_NAME", "Generic ML Boilerplate")
    )
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    debug: bool = field(default_factory=lambda: _read_bool(os.getenv("DEBUG", "false")))
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "sqlite:///generic_ml.db"
        )
    )
    ml_model_path: Path = field(
        default_factory=lambda: _read_path("ML_MODEL_PATH", "backend/app/ml/artifacts/model.joblib")
    )
    ml_model_identifier: str = field(
        default_factory=lambda: os.getenv("ML_MODEL_IDENTIFIER", "generic-ml-model")
    )
    ml_model_version: str = field(
        default_factory=lambda: os.getenv("ML_MODEL_VERSION", "unknown")
    )


def get_settings() -> Settings:
    return Settings()
