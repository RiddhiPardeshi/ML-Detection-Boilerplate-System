import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.security import create_session_token, verify_password
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import AuditLog, FileRecord, User, UserRole
from backend.app.services.auth import register_user
from backend.app.schemas.auth import RegisterRequest


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


@pytest.fixture
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    resp = register_user(
        db_session,
        RegisterRequest(
            username="profileuser",
            email="profile@example.com",
            password="originalpassword123",
        ),
    )
    user = db_session.get(User, resp.id)
    return user


@pytest.fixture
def user_token(test_user):
    return create_session_token(test_user.id)


def test_1_unauthenticated_profile_access_rejected(client):
    res1 = client.get("/auth/me")
    assert res1.status_code == 401

    res2 = client.put("/auth/profile", json={"username": "newname"})
    assert res2.status_code == 401

    res3 = client.post(
        "/auth/change-password",
        json={
            "current_password": "p",
            "new_password": "n",
            "confirm_new_password": "n",
        },
    )
    assert res3.status_code == 401


def test_2_authenticated_user_can_view_own_profile(client, user_token):
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "profileuser"
    assert data["email"] == "profile@example.com"


def test_3_profile_contains_real_user_data(client, test_user, user_token):
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == test_user.id
    assert data["username"] == test_user.username
    assert data["email"] == test_user.email
    assert data["role"] == "USER"
    assert data["is_active"] is True
    assert "created_at" in data
    assert "last_login" in data


def test_4_profile_update_works(client, db_session, test_user, user_token):
    payload = {"username": "updatedname", "email": "updated@example.com"}
    res = client.put("/auth/profile", json=payload, headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "updatedname"
    assert data["email"] == "updated@example.com"

    db_session.expire_all()
    db_user = db_session.get(User, test_user.id)
    assert db_user.username == "updatedname"
    assert db_user.email == "updated@example.com"


def test_5_user_cannot_modify_another_user(client, db_session, test_user, user_token):
    user2 = register_user(
        db_session,
        RegisterRequest(
            username="otheruser",
            email="other@example.com",
            password="otherpassword123",
        ),
    )

    client.put("/auth/profile", json={"username": "myname"}, headers={"Authorization": f"Bearer {user_token}"})

    db_session.expire_all()
    other_db = db_session.get(User, user2.id)
    assert other_db.username == "otheruser"


def test_6_role_cannot_be_escalated(client, test_user, user_token):
    payload = {"username": "hacker", "role": "ADMIN"}
    res = client.put("/auth/profile", json=payload, headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "USER"


def test_7_invalid_profile_data_rejected(client, user_token):
    res = client.put("/auth/profile", json={"email": "notanemail"}, headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 400

    client.post("/auth/register", json={"username": "userb", "email": "b@ex.com", "password": "pass"})
    res_dup = client.put("/auth/profile", json={"username": "userb"}, headers={"Authorization": f"Bearer {user_token}"})
    assert res_dup.status_code == 409


def test_8_wrong_current_password_rejected(client, user_token):
    payload = {
        "current_password": "wrongpassword",
        "new_password": "newpassword123",
        "confirm_new_password": "newpassword123",
    }
    res = client.post("/auth/change-password", json=payload, headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 400
    assert "incorrect" in res.json()["detail"].lower()


def test_9_password_confirmation_mismatch_rejected(client, user_token):
    payload = {
        "current_password": "originalpassword123",
        "new_password": "newpassword123",
        "confirm_new_password": "mismatchpassword",
    }
    res = client.post("/auth/change-password", json=payload, headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 400
    assert "match" in res.json()["detail"].lower()


def test_10_successful_password_change_works(client, db_session, test_user, user_token):
    payload = {
        "current_password": "originalpassword123",
        "new_password": "newpassword123",
        "confirm_new_password": "newpassword123",
    }
    res = client.post("/auth/change-password", json=payload, headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "session_token" in data

    db_session.expire_all()
    db_user = db_session.get(User, test_user.id)
    assert verify_password("newpassword123", db_user.password_hash)


def test_11_password_is_never_exposed_in_responses(client, user_token):
    res_me = client.get("/auth/me", headers={"Authorization": f"Bearer {user_token}"})
    data = res_me.json()
    assert "password" not in data
    assert "password_hash" not in data


def test_12_appropriate_audit_event_created(client, db_session, test_user, user_token):
    client.put("/auth/profile", json={"username": "auditeduser"}, headers={"Authorization": f"Bearer {user_token}"})

    logs = db_session.query(AuditLog).filter_by(user_id=test_user.id).all()
    action_categories = [l.action_category for l in logs]
    assert "Profile Updated" in action_categories


def test_13_existing_ml_detect_still_works(client, user_token):
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="green")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="JPEG")
    img_bytes = img_byte_arr.getvalue()

    files = {"file": ("test_detect_p8.jpg", img_bytes, "image/jpeg")}
    headers = {"Authorization": f"Bearer {user_token}"}

    res = client.post("/ml/detect", files=files, headers=headers)
    assert res.status_code == 200
    assert "prediction_id" in res.json()


def test_14_existing_ml_predict_still_works(client, monkeypatch):
    from backend.app.api import ml as ml_api
    from backend.app.ml.models import TabularModel

    class DummyModel(TabularModel):
        def fit(self, X, y):
            return self

        def predict(self, X):
            return [1]

        def predict_proba(self, X):
            return [[0.1, 0.9]]

    monkeypatch.setattr(ml_api, "load_model", lambda path: (DummyModel(), None))

    payload = {"features": {"feature1": 1.0, "feature2": 2.0}}
    res = client.post("/ml/predict", json=payload)
    assert res.status_code == 200
    assert "prediction" in res.json()


def test_15_files_repository_still_works(client, user_token):
    res = client.get("/files", headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 200


def test_16_system_logs_still_works(client, user_token):
    res = client.get("/audit-logs", headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 200


def test_17_dashboard_still_works(client, user_token):
    res = client.get("/ml/stats", headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 200
