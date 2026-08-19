from unittest.mock import Mock

import pandas as pd

from backend.app.ml.models import TabularModel
from backend.app.ml.preprocessing import TabularPreprocessor
from backend.app.ml.training import train_model


class RecordingModel(TabularModel):
    def __init__(self):
        self.fit_calls = []

    def fit(self, X, y):
        self.fit_calls.append((X, y))
        return self

    def predict(self, X):
        return [0] * len(X)


def test_training_without_preprocessor_uses_training_data():
    model = RecordingModel()
    X_train = [[1], [2]]
    y_train = [0, 1]

    trained_model, fitted_preprocessor = train_model(model, X_train, y_train)

    assert trained_model is model
    assert fitted_preprocessor is None
    assert model.fit_calls == [(X_train, y_train)]


def test_training_with_unfitted_preprocessor_fits_and_transforms():
    model = RecordingModel()
    preprocessor = TabularPreprocessor(numeric_features=["value"])
    X_train = pd.DataFrame({"value": [1.0, 2.0]})
    y_train = [0, 1]

    trained_model, returned_preprocessor = train_model(model, X_train, y_train, preprocessor)

    assert trained_model is model
    assert returned_preprocessor is preprocessor
    assert preprocessor.transformer_ is not None
    assert model.fit_calls[0][0].shape == (2, 1)
    assert model.fit_calls[0][1] is y_train


def test_training_with_fitted_preprocessor_does_not_refit():
    model = RecordingModel()
    preprocessor = TabularPreprocessor(numeric_features=["value"])
    X_train = pd.DataFrame({"value": [1.0, 2.0]})
    preprocessor.fit(X_train)
    fit_mock = Mock(side_effect=AssertionError("preprocessor was refit"))
    preprocessor.fit = fit_mock

    train_model(model, X_train, [0, 1], preprocessor)

    fit_mock.assert_not_called()
    assert len(model.fit_calls) == 1
