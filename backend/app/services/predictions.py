from typing import Any

from sqlalchemy.orm import Session

from ..models import Prediction, User


def save_prediction(
    db: Session,
    prediction_value: Any,
    probability: Any | None,
    model_identifier: str,
    model_version: str,
    user: User | None = None,
) -> Prediction:
    """Persist prediction output and optional requesting user association."""
    record = Prediction(
        prediction_value=prediction_value,
        probability=probability,
        model_identifier=model_identifier,
        model_version=model_version,
        user=user,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
