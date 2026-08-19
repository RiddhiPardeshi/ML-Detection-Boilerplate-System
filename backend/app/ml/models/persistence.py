from pathlib import Path
from typing import Any, TypedDict

import joblib

from ..preprocessing import TabularPreprocessor
from .base import TabularModel


class ModelArtifact(TypedDict):
    model: TabularModel
    preprocessor: TabularPreprocessor | None


def save_model(
    model: TabularModel,
    path: str | Path,
    preprocessor: TabularPreprocessor | None = None,
) -> None:
    """Persist a model and optional fitted preprocessor as one joblib artifact."""
    if not isinstance(model, TabularModel):
        raise TypeError("model must be an instance of TabularModel")
    if preprocessor is not None and not isinstance(preprocessor, TabularPreprocessor):
        raise TypeError("preprocessor must be a TabularPreprocessor or None")

    artifact_path = Path(path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact: ModelArtifact = {"model": model, "preprocessor": preprocessor}
    try:
        joblib.dump(artifact, artifact_path)
    except Exception as error:
        raise RuntimeError(f"Unable to save model artifact '{artifact_path}': {error}") from error


def load_model(path: str | Path) -> tuple[TabularModel, TabularPreprocessor | None]:
    """Load a model and optional preprocessor from a joblib artifact."""
    artifact_path = Path(path)
    if not artifact_path.exists() or not artifact_path.is_file():
        raise FileNotFoundError(f"Model artifact not found: {artifact_path}")

    try:
        artifact: Any = joblib.load(artifact_path)
    except Exception as error:
        raise RuntimeError(f"Unable to read model artifact '{artifact_path}': {error}") from error

    if not isinstance(artifact, dict) or set(artifact) != {"model", "preprocessor"}:
        raise RuntimeError("Invalid model artifact: expected model and preprocessor entries")
    model = artifact["model"]
    preprocessor = artifact["preprocessor"]
    if not isinstance(model, TabularModel):
        raise RuntimeError("Invalid model artifact: model is not a TabularModel")
    if preprocessor is not None and not isinstance(preprocessor, TabularPreprocessor):
        raise RuntimeError("Invalid model artifact: preprocessor has an unsupported type")
    return model, preprocessor
