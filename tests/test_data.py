import pandas as pd
import pytest

from backend.app.ml.data import load_csv, split_dataset


def test_load_csv_returns_dataframe(tmp_path):
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("feature,label\n1,A\n2,B\n", encoding="utf-8")

    result = load_csv(csv_path)

    assert isinstance(result, pd.DataFrame)
    assert result.to_dict(orient="records") == [
        {"feature": 1, "label": "A"},
        {"feature": 2, "label": "B"},
    ]


def test_load_csv_missing_file_raises_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="CSV dataset file not found"):
        load_csv(tmp_path / "missing.csv")


def test_split_dataset_returns_four_subsets():
    X = pd.DataFrame({"feature": range(10)})
    y = pd.Series(range(10))

    X_train, X_test, y_train, y_test = split_dataset(X, y, stratify=False)

    assert len(X_train) == 8
    assert len(X_test) == 2
    assert len(y_train) == 8
    assert len(y_test) == 2


def test_split_dataset_stratifies_class_labels():
    X = pd.DataFrame({"feature": range(20)})
    y = pd.Series(["A"] * 10 + ["B"] * 10)

    _, X_test, _, y_test = split_dataset(X, y)

    assert len(X_test) == 4
    assert y_test.value_counts().to_dict() == {"A": 2, "B": 2}
