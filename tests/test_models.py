import inspect

import pytest

from backend.app.ml.models import TabularModel


def test_tabular_model_is_abstract():
    assert inspect.isabstract(TabularModel)


class IncompleteModel(TabularModel):
    def fit(self, X, y):
        return self


def test_fit_and_predict_are_required():
    with pytest.raises(TypeError):
        IncompleteModel()


class CompleteModel(TabularModel):
    def fit(self, X, y):
        return self

    def predict(self, X):
        return X


def test_complete_model_can_implement_contract():
    model = CompleteModel()
    assert model.fit([], []) is model
    assert model.predict([1]) == [1]
