import pandas as pd

from backend.app.ml.preprocessing import TabularPreprocessor


def test_numeric_preprocessing_imputes_and_scales():
    data = pd.DataFrame({"age": [10.0, None, 30.0]})
    preprocessor = TabularPreprocessor(numeric_features=["age"])

    transformed = preprocessor.fit_transform(data)

    assert transformed.shape == (3, 1)
    assert transformed[1, 0] == 0.0
    assert abs(transformed[:, 0].mean()) < 1e-9


def test_categorical_preprocessing_imputes_and_encodes():
    data = pd.DataFrame({"color": ["red", None, "blue"]})
    preprocessor = TabularPreprocessor(categorical_features=["color"])

    transformed = preprocessor.fit_transform(data)

    assert transformed.shape == (3, 2)
    assert preprocessor.transformer_ is not None


def test_fit_then_transform_reuses_fitted_transformer():
    training = pd.DataFrame({"value": [1.0, 2.0]})
    new_data = pd.DataFrame({"value": [3.0]})
    preprocessor = TabularPreprocessor()

    preprocessor.fit(training)
    fitted_transformer = preprocessor.transformer_
    transformed = preprocessor.transform(new_data)

    assert preprocessor.transformer_ is fitted_transformer
    assert transformed.shape == (1, 1)


def test_unknown_categories_are_ignored():
    training = pd.DataFrame({"color": ["red", "blue"]})
    new_data = pd.DataFrame({"color": ["green"]})
    preprocessor = TabularPreprocessor(categorical_features=["color"])

    preprocessor.fit(training)
    transformed = preprocessor.transform(new_data)

    assert transformed.shape == (1, 2)
    dense_transformed = transformed.toarray() if hasattr(transformed, "toarray") else transformed
    assert dense_transformed.tolist() == [[0.0, 0.0]]
