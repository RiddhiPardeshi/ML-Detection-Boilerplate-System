import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import AuditLog, User
from backend.app.core.security import create_session_token, decode_session_token


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


def test_session_token_generation_and_decoding():
    token = create_session_token(42)
    assert token is not None
    user_id = decode_session_token(token)
    assert user_id == 42


def test_register_and_login_flow(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)

    try:
        # 1. Register user
        reg_response = client.post(
            "/auth/register",
            json={
                "username": "phase1user",
                "email": "phase1@example.com",
                "password": "Password123!",
            },
        )
        assert reg_response.status_code == 201
        data = reg_response.json()
        assert data["username"] == "phase1user"
        assert data["email"] == "phase1@example.com"
        assert "session_token" in data and data["session_token"] is not None

        # Verify audit log created
        audit_reg = db_session.scalar(
            select(AuditLog).where(AuditLog.action_category == "Register")
        )
        assert audit_reg is not None
        assert audit_reg.username == "phase1user"

        # 2. Login with wrong password
        login_fail = client.post(
            "/auth/login",
            json={"email": "phase1@example.com", "password": "WrongPassword"},
        )
        assert login_fail.status_code == 401
        audit_fail = db_session.scalar(
            select(AuditLog).where(AuditLog.action_category == "Login Failed")
        )
        assert audit_fail is not None

        # 3. Login with correct password
        login_success = client.post(
            "/auth/login",
            json={"email": "phase1@example.com", "password": "Password123!"},
        )
        assert login_success.status_code == 200
        token = login_success.json()["session_token"]

        audit_ok = db_session.scalar(
            select(AuditLog).where(AuditLog.action_category == "Login Success")
        )
        assert audit_ok is not None
        assert audit_ok.username == "phase1user"

        # Check last_login updated
        user = db_session.scalar(select(User).where(User.username == "phase1user"))
        assert user.last_login is not None

        # 4. Get /auth/me with session header
        me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["username"] == "phase1user"

        # 5. Logout
        logout_resp = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert logout_resp.status_code == 200
        audit_logout = db_session.scalar(
            select(AuditLog).where(AuditLog.action_category == "Logout")
        )
        assert audit_logout is not None
    finally:
        app.dependency_overrides.clear()
