from unittest.mock import Mock

import pytest

from backend.app.ml.inference import predict, predict_proba
from backend.app.ml.models import TabularModel
from backend.app.ml.preprocessing import TabularPreprocessor


class InferenceModel(TabularModel):
    def __init__(self, probabilities=None):
        self.received_X = None
        self.probabilities = probabilities
        self.fit_called = False

    def fit(self, X, y):
        self.fit_called = True
        return self

    def predict(self, X):
        self.received_X = X
        return ["class-a"]

    def predict_proba(self, X):
        self.received_X = X
        return self.probabilities


class TransformingPreprocessor(TabularPreprocessor):
    def __init__(self, transformed):
        super().__init__()
        self.transformed = transformed
        self.fit = Mock()
        self.fit_transform = Mock()
        self.transform = Mock(return_value=transformed)


def test_prediction_without_preprocessor_passes_input_directly():
    model = InferenceModel()
    features = [[1, 2]]

    assert predict(model, features) == ["class-a"]
    assert model.received_X is features
    assert model.fit_called is False


def test_prediction_with_preprocessor_only_transforms():
    model = InferenceModel()
    preprocessor = TransformingPreprocessor([[10, 20]])
    features = [[1, 2]]

    result = predict(model, features, preprocessor)

    assert result == ["class-a"]
    preprocessor.transform.assert_called_once_with(features)
    preprocessor.fit.assert_not_called()
    preprocessor.fit_transform.assert_not_called()
    assert model.received_X == [[10, 20]]


def test_probability_prediction_when_supported():
    model = InferenceModel([[0.25, 0.75]])

    assert predict_proba(model, [[1]]) == [[0.25, 0.75]]


def test_probability_prediction_without_support_raises_clear_error():
    class NoProbabilityModel(InferenceModel):
        predict_proba = TabularModel.predict_proba

    with pytest.raises(RuntimeError, match="does not support probability"):
        predict_proba(NoProbabilityModel(), [[1]])
