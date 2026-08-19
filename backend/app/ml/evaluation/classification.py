from typing import Any, TypedDict

from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from ..models import TabularModel
from ..preprocessing import TabularPreprocessor


class ClassificationEvaluation(TypedDict):
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    confusion_matrix: Any


def evaluate_classification(
    model: TabularModel,
    X_test: Any,
    y_test: Any,
    preprocessor: TabularPreprocessor | None = None,
) -> ClassificationEvaluation:
    """Evaluate a trained classification model on held-out test data."""
    X_evaluation = preprocessor.transform(X_test) if preprocessor is not None else X_test
    predictions = model.predict(X_evaluation)

    return {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "precision": float(
            precision_score(y_test, predictions, average="weighted", zero_division=0)
        ),
        "recall": float(recall_score(y_test, predictions, average="weighted", zero_division=0)),
        "f1_score": float(f1_score(y_test, predictions, average="weighted", zero_division=0)),
        "confusion_matrix": confusion_matrix(y_test, predictions),
    }
