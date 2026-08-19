from typing import Any

from ..models import TabularModel
from ..preprocessing import TabularPreprocessor


def predict(
    model: TabularModel,
    X: Any,
    preprocessor: TabularPreprocessor | None = None,
) -> Any:
    """Transform new input when configured, then generate model predictions."""
    prepared_input = _prepare_input(model, X, preprocessor)
    return model.predict(prepared_input)


def predict_proba(
    model: TabularModel,
    X: Any,
    preprocessor: TabularPreprocessor | None = None,
) -> Any:
    """Transform new input when configured, then generate probabilities."""
    prepared_input = _prepare_input(model, X, preprocessor)
    try:
        return model.predict_proba(prepared_input)
    except NotImplementedError as error:
        raise RuntimeError("Model does not support probability prediction") from error


def _prepare_input(
    model: TabularModel,
    X: Any,
    preprocessor: TabularPreprocessor | None,
) -> Any:
    if not isinstance(model, TabularModel):
        raise TypeError("model must be an instance of TabularModel")
    if X is None:
        raise ValueError("Inference input X cannot be None")
    if preprocessor is not None:
        if not isinstance(preprocessor, TabularPreprocessor):
            raise TypeError("preprocessor must be a TabularPreprocessor or None")
        return preprocessor.transform(X)
    return X
