from typing import Any

from ..models import TabularModel
from ..preprocessing import TabularPreprocessor


def train_model(
    model: TabularModel,
    X_train: Any,
    y_train: Any,
    preprocessor: TabularPreprocessor | None = None,
) -> tuple[TabularModel, TabularPreprocessor | None]:
    """Fit a model using training data and an optional reusable preprocessor."""
    X_prepared = X_train
    if preprocessor is not None:
        if preprocessor.transformer_ is None:
            preprocessor.fit(X_train)
        X_prepared = preprocessor.transform(X_train)

    model.fit(X_prepared, y_train)
    return model, preprocessor
