from pathlib import Path

from backend.app.config.settings import Settings, get_settings


def test_settings_load_environment(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Test Application")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://<user>:<password>@<host>/test")
    monkeypatch.setenv("ML_MODEL_PATH", "~/models/model.joblib")
    monkeypatch.setenv("ML_MODEL_IDENTIFIER", "test-model")
    monkeypatch.setenv("ML_MODEL_VERSION", "v2")

    settings = get_settings()

    assert settings.app_name == "Test Application"
    assert settings.app_env == "test"
    assert settings.debug is True
    assert settings.database_url.startswith("postgresql://")
    assert settings.ml_model_path == Path("~/models/model.joblib").expanduser()
    assert settings.ml_model_identifier == "test-model"
    assert settings.ml_model_version == "v2"


def test_settings_defaults_are_non_sensitive(monkeypatch):
    for variable in (
        "APP_NAME",
        "APP_ENV",
        "DEBUG",
        "DATABASE_URL",
        "ML_MODEL_PATH",
        "ML_MODEL_IDENTIFIER",
        "ML_MODEL_VERSION",
    ):
        monkeypatch.delenv(variable, raising=False)

    settings = Settings()

    assert settings.app_env == "development"
    assert settings.debug is False
    assert settings.database_url == "sqlite:///generic_ml.db"
    assert "@" not in settings.database_url


def test_model_path_is_normalized(monkeypatch, tmp_path):
    model_path = tmp_path / "nested" / "model.joblib"
    monkeypatch.setenv("ML_MODEL_PATH", str(model_path))

    settings = get_settings()

    assert isinstance(settings.ml_model_path, Path)
    assert settings.ml_model_path == model_path
