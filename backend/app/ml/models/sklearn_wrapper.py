"""Wrapper classes for sklearn models to satisfy TabularModel interface."""

from .base import TabularModel


class SklearnModelWrapper(TabularModel):
    """Wraps sklearn models to satisfy TabularModel interface."""
    
    def __init__(self, sklearn_model):
        self.sklearn_model = sklearn_model
    
    def fit(self, X, y):
        self.sklearn_model.fit(X, y)
        return self
    
    def predict(self, X):
        return self.sklearn_model.predict(X)
    
    def predict_proba(self, X):
        if hasattr(self.sklearn_model, 'predict_proba'):
            return self.sklearn_model.predict_proba(X)
        raise NotImplementedError("Model does not support probability prediction")
