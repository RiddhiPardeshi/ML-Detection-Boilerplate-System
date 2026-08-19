from collections.abc import Sequence

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


class TabularPreprocessor:
    """Reusable numeric and categorical preprocessing for tabular data."""

    def __init__(
        self,
        numeric_features: Sequence[str] | None = None,
        categorical_features: Sequence[str] | None = None,
    ) -> None:
        self.numeric_features = list(numeric_features) if numeric_features is not None else None
        self.categorical_features = (
            list(categorical_features) if categorical_features is not None else None
        )
        self.transformer_: ColumnTransformer | None = None
        self.numeric_features_: list[str] = []
        self.categorical_features_: list[str] = []

    def fit(self, X: pd.DataFrame, y: object | None = None) -> "TabularPreprocessor":
        self._validate_input(X)
        numeric_features, categorical_features = self._resolve_features(X)
        prepared_X = self._prepare_input(X, categorical_features)

        transformers = []
        if numeric_features:
            numeric_pipeline = Pipeline(
                steps=[
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scaler", StandardScaler()),
                ]
            )
            transformers.append(("numeric", numeric_pipeline, numeric_features))

        if categorical_features:
            categorical_pipeline = Pipeline(
                steps=[
                    ("imputer", SimpleImputer(strategy="most_frequent")),
                    ("encoder", OneHotEncoder(handle_unknown="ignore")),
                ]
            )
            transformers.append(("categorical", categorical_pipeline, categorical_features))

        if not transformers:
            raise ValueError("At least one numeric or categorical feature is required")

        self.transformer_ = ColumnTransformer(transformers=transformers, remainder="drop")
        self.transformer_.fit(prepared_X, y)
        self.numeric_features_ = numeric_features
        self.categorical_features_ = categorical_features
        return self

    def transform(self, X: pd.DataFrame):
        self._validate_input(X)
        if self.transformer_ is None:
            raise RuntimeError("TabularPreprocessor must be fitted before transform")
        prepared_X = self._prepare_input(X, self.categorical_features_)
        return self.transformer_.transform(prepared_X)

    def fit_transform(self, X: pd.DataFrame, y: object | None = None):
        self.fit(X, y)
        return self.transform(X)

    def _resolve_features(self, X: pd.DataFrame) -> tuple[list[str], list[str]]:
        columns = list(X.columns)
        numeric_features = (
            list(self.numeric_features)
            if self.numeric_features is not None
            else X.select_dtypes(include="number").columns.tolist()
        )
        categorical_features = (
            list(self.categorical_features)
            if self.categorical_features is not None
            else [column for column in columns if column not in numeric_features]
        )

        selected_features = numeric_features + categorical_features
        missing_features = [column for column in selected_features if column not in columns]
        if missing_features:
            raise ValueError(f"Features not found in input data: {missing_features}")
        if set(numeric_features).intersection(categorical_features):
            raise ValueError("Numeric and categorical features must not overlap")
        return numeric_features, categorical_features

    @staticmethod
    def _validate_input(X: pd.DataFrame) -> None:
        if not isinstance(X, pd.DataFrame):
            raise TypeError("TabularPreprocessor expects a pandas DataFrame")

    @staticmethod
    def _prepare_input(X: pd.DataFrame, categorical_features: Sequence[str]) -> pd.DataFrame:
        prepared_X = X.copy()
        if categorical_features:
            prepared_X[list(categorical_features)] = prepared_X[
                list(categorical_features)
            ].replace({None: float("nan")})
        return prepared_X
