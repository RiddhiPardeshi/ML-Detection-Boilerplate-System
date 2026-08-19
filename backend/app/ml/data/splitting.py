from typing import Any

from sklearn.model_selection import train_test_split


def split_dataset(
    X: Any,
    y: Any,
    test_size: float = 0.2,
    random_state: int = 42,
    stratify: bool = True,
) -> tuple[Any, Any, Any, Any]:
    """Split feature data and labels into train and test subsets."""
    stratify_labels = y if stratify else None
    try:
        return train_test_split(
            X,
            y,
            test_size=test_size,
            random_state=random_state,
            stratify=stratify_labels,
        )
    except ValueError:
        if not stratify:
            raise
        return train_test_split(
            X,
            y,
            test_size=test_size,
            random_state=random_state,
            stratify=None,
        )
