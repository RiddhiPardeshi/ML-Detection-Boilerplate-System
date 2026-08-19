from pathlib import Path

import pandas as pd
import pytest

from backend.app.ml.models import TabularModel, load_model, save_model
from backend.app.ml.preprocessing import TabularPreprocessor


class PersistableModel(TabularModel):
    def fit(self, X, y):
        return self

    def predict(self, X):
        return [0] * len(X)


def test_save_and_load_model_with_optional_preprocessor(tmp_path):
    model = PersistableModel()
    preprocessor = TabularPreprocessor(numeric_features=["value"])
    preprocessor.fit(pd.DataFrame({"value": [1.0, 2.0]}))
    artifact_path = tmp_path / "nested" / "model.joblib"

    save_model(model, artifact_path, preprocessor)
    loaded_model, loaded_preprocessor = load_model(artifact_path)

    assert isinstance(loaded_model, PersistableModel)
    assert isinstance(loaded_preprocessor, TabularPreprocessor)
    assert loaded_preprocessor.transformer_ is not None
    assert artifact_path.exists()


def test_load_model_missing_artifact(tmp_path):
    with pytest.raises(FileNotFoundError, match="Model artifact not found"):
        load_model(tmp_path / "missing.joblib")


def test_load_model_invalid_artifact(tmp_path):
    artifact_path = tmp_path / "invalid.joblib"
    artifact_path.write_text("not a joblib artifact", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Unable to read model artifact"):
        load_model(artifact_path)
