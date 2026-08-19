from pathlib import Path

import pandas as pd


def load_csv(file_path: str | Path) -> pd.DataFrame:
    """Load a CSV file into a pandas DataFrame."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV dataset file not found: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"CSV dataset path is not a file: {path}")

    try:
        return pd.read_csv(path)
    except Exception as error:
        raise RuntimeError(f"Unable to read CSV dataset '{path}': {error}") from error
