import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.security import create_session_token
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import AuditLog, Prediction, User, UserRole
from backend.app.services.audit import log_audit_event


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_dashboard_stats_requires_auth():
    client = TestClient(app)
    response = client.get("/ml/stats")
    assert response.status_code == 401


def test_dashboard_stats_returns_real_data(db_session):
    # 1. Create a user
    user = User(
        username="dashuser",
        email="dash@example.com",
        password_hash="hashedpass",
        role=UserRole.USER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # 2. Add real predictions for user
    pred1 = Prediction(
        prediction_value=[1],
        probability=[[0.2, 0.8]],
        model_identifier="generic-ml-model",
        model_version="1.0",
        user=user,
    )
    pred2 = Prediction(
        prediction_value=[0],
        probability=[[0.9, 0.1]],
        model_identifier="generic-ml-model",
        model_version="1.0",
        user=user,
    )
    db_session.add_all([pred1, pred2])

    # 3. Add audit logs
    log_audit_event(
        db=db_session,
        action_category="Login Success",
        user_id=user.id,
        username=user.username,
        source_ip="127.0.0.1",
        transaction_details="User logged in",
    )

    token = create_session_token(user.id)

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)

    try:
        response = client.get("/ml/stats", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

        data = response.json()
        assert data["total_inferences"] == 2
        assert data["average_confidence"] is None
        assert data["storage_bytes"] is None
        assert data["classification_summary"] == {"[1]": 1, "[0]": 1}
        assert len(data["recent_predictions"]) == 2
        assert len(data["audit_timeline"]) == 1
        assert data["audit_timeline"][0]["action_category"] == "Login Success"
    finally:
        app.dependency_overrides.clear()
