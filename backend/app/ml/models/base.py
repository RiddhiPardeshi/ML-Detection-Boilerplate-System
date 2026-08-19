from abc import ABC, abstractmethod
from typing import Any


class TabularModel(ABC):
    """Base interface for sklearn-compatible tabular ML models."""

    @abstractmethod
    def fit(self, X: Any, y: Any) -> "TabularModel":
        """Fit the model using feature data and target values."""
        raise NotImplementedError

    @abstractmethod
    def predict(self, X: Any) -> Any:
        """Generate predictions for feature data."""
        raise NotImplementedError

    def predict_proba(self, X: Any) -> Any:
        """Generate probabilities when the concrete model supports them."""
        raise NotImplementedError("This model does not support probability prediction")
