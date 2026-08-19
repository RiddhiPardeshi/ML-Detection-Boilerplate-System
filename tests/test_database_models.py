from sqlalchemy import inspect

from backend.app.database import Base
from backend.app.models import Prediction, User


def test_prediction_metadata_has_expected_columns_and_foreign_key():
    columns = Prediction.__table__.columns

    assert set(columns.keys()) == {
        "id",
        "prediction_value",
        "probability",
        "model_identifier",
        "model_version",
        "user_id",
        "created_at",
    }
    assert columns["id"].primary_key is True
    assert columns["prediction_value"].nullable is False
    assert columns["user_id"].nullable is True
    assert {str(foreign_key.column) for foreign_key in columns["user_id"].foreign_keys} == {
        "users.id"
    }


def test_user_prediction_relationship_metadata_exists():
    user_relationship = inspect(User).relationships["predictions"]
    prediction_relationship = inspect(Prediction).relationships["user"]

    assert user_relationship.mapper.class_ is Prediction
    assert prediction_relationship.mapper.class_ is User
    assert prediction_relationship.local_remote_pairs


def test_metadata_inspection_does_not_create_tables():
    assert "users" in Base.metadata.tables
    assert "predictions" in Base.metadata.tables
