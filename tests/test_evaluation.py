import numpy as np

from backend.app.ml.evaluation import evaluate_classification
from backend.app.ml.models import TabularModel


class FixedPredictionModel(TabularModel):
    def __init__(self, predictions):
        self.predictions = predictions
        self.received_X = None

    def fit(self, X, y):
        return self

    def predict(self, X):
        self.received_X = X
        return np.array(self.predictions)


def test_classification_evaluation_returns_metrics():
    model = FixedPredictionModel([0, 1, 1, 0])
    y_test = np.array([0, 1, 0, 0])

    results = evaluate_classification(model, [[1], [2], [3], [4]], y_test)

    assert results["accuracy"] == 0.75
    assert results["precision"] == 0.875
    assert results["recall"] == 0.75
    assert round(results["f1_score"], 6) == round(0.7666666666666666, 6)
    assert results["confusion_matrix"].tolist() == [[2, 1], [0, 1]]


def test_evaluation_handles_zero_division():
    model = FixedPredictionModel([0, 0, 0])
    y_test = np.array([0, 0, 0])

    results = evaluate_classification(model, [[1], [2], [3]], y_test)

    assert results["precision"] == 1.0
    assert results["recall"] == 1.0
    assert results["f1_score"] == 1.0
    assert results["confusion_matrix"].tolist() == [[3]]


def test_evaluation_transforms_test_data_without_fitting():
    class TransformOnlyPreprocessor:
        def __init__(self):
            self.fit_called = False

        def fit(self, X):
            self.fit_called = True
            raise AssertionError("preprocessor was fitted")

        def transform(self, X):
            return [[value * 2] for value in X]

    model = FixedPredictionModel([1, 0])
    preprocessor = TransformOnlyPreprocessor()

    evaluate_classification(model, [1, 2], [1, 0], preprocessor)

    assert preprocessor.fit_called is False
    assert model.received_X == [[2], [4]]
