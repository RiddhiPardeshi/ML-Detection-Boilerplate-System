import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.security import create_session_token
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import FileRecord, User, UserRole
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
def user_a(db_session):
    user = User(
        username="usera",
        email="usera@example.com",
        password_hash="hashedpassa",
        role=UserRole.USER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_b(db_session):
    user = User(
        username="userb",
        email="userb@example.com",
        password_hash="hashedpassb",
        role=UserRole.USER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session):
    user = User(
        username="adminuser",
        email="admin@example.com",
        password_hash="hashedpassadmin",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def token_a(user_a):
    return create_session_token(user_a.id)


@pytest.fixture
def token_b(user_b):
    return create_session_token(user_b.id)


@pytest.fixture
def token_admin(admin_user):
    return create_session_token(admin_user.id)


def test_1_unauthenticated_access_rejected(client):
    res = client.get("/audit-logs")
    assert res.status_code == 401


def test_2_authenticated_user_can_view_own_logs(client, db_session, user_a, token_a):
    log_audit_event(
        db=db_session,
        action_category="Login Success",
        user_id=user_a.id,
        username=user_a.username,
        source_ip="127.0.0.1",
        transaction_details="User A logged in",
    )

    res = client.get("/audit-logs", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["username"] == "usera"
    assert data["items"][0]["action_category"] == "Login Success"


def test_3_user_cannot_view_another_user_logs(client, db_session, user_a, user_b, token_b):
    log_audit_event(
        db=db_session,
        action_category="Login Success",
        user_id=user_a.id,
        username=user_a.username,
        transaction_details="User A activity",
    )
    log_audit_event(
        db=db_session,
        action_category="Login Success",
        user_id=user_b.id,
        username=user_b.username,
        transaction_details="User B activity",
    )

    # User B requests logs, explicitly trying to query usera
    res = client.get("/audit-logs?username=usera", headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 200
    data = res.json()
    # User B should only see User B's 1 log entry
    assert data["total"] == 1
    assert data["items"][0]["username"] == "userb"


def test_4_admin_access_follows_existing_authorization(client, db_session, user_a, user_b, token_admin):
    log_audit_event(
        db=db_session,
        action_category="Predict",
        user_id=user_a.id,
        username=user_a.username,
    )
    log_audit_event(
        db=db_session,
        action_category="Login Success",
        user_id=user_b.id,
        username=user_b.username,
    )

    res = client.get("/audit-logs", headers={"Authorization": f"Bearer {token_admin}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2


def test_5_logs_contain_real_database_records(client, db_session, user_a, token_a):
    log_audit_event(
        db=db_session,
        action_category="Predict",
        user_id=user_a.id,
        username=user_a.username,
        source_ip="192.168.1.50",
        transaction_details="Real inference execution",
    )

    res = client.get("/audit-logs", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    data = res.json()
    item = data["items"][0]
    assert item["source_ip"] == "192.168.1.50"
    assert item["transaction_details"] == "Real inference execution"


def test_6_pagination_works(client, db_session, user_a, token_a):
    for i in range(5):
        log_audit_event(
            db=db_session,
            action_category="Predict",
            user_id=user_a.id,
            username=user_a.username,
            transaction_details=f"Inference #{i}",
        )

    res1 = client.get("/audit-logs?page=1&limit=2", headers={"Authorization": f"Bearer {token_a}"})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["total"] == 5
    assert data1["page"] == 1
    assert data1["limit"] == 2
    assert data1["pages"] == 3
    assert len(data1["items"]) == 2

    res2 = client.get("/audit-logs?page=2&limit=2", headers={"Authorization": f"Bearer {token_a}"})
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["items"]) == 2
    assert data2["items"][0]["id"] != data1["items"][0]["id"]


def test_7_filtering_works(client, db_session, user_a, token_a):
    log_audit_event(
        db=db_session,
        action_category="Login Success",
        user_id=user_a.id,
        username=user_a.username,
    )
    log_audit_event(
        db=db_session,
        action_category="Predict",
        user_id=user_a.id,
        username=user_a.username,
    )

    res = client.get("/audit-logs?action=Login", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["action_category"] == "Login Success"


def test_8_sensitive_fields_not_exposed(client, db_session, user_a, token_a):
    log_audit_event(
        db=db_session,
        action_category="Login Failed",
        user_id=user_a.id,
        username=user_a.username,
        transaction_details="Invalid password submitted",
    )

    res = client.get("/audit-logs", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    data = res.json()
    item = data["items"][0]
    assert "password" not in item
    assert "session_token" not in item
    assert "password_hash" not in item


def test_9_empty_logs_handled_correctly(client, user_a, token_a):
    res = client.get("/audit-logs", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["pages"] == 1


def test_10_existing_ml_detect_still_works(client, db_session, user_a, token_a):
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="blue")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="JPEG")
    img_bytes = img_byte_arr.getvalue()

    files = {"file": ("test_detect_p7.jpg", img_bytes, "image/jpeg")}
    headers = {"Authorization": f"Bearer {token_a}"}

    res = client.post("/ml/detect", files=files, headers=headers)
    assert res.status_code == 200
    assert "prediction_id" in res.json()

    audit_res = client.get("/audit-logs", headers=headers)
    assert audit_res.status_code == 200
    assert audit_res.json()["total"] >= 1


def test_11_existing_ml_predict_still_works(client, db_session, monkeypatch):
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


def test_12_existing_files_repository_still_works(client, db_session, user_a, token_a):
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    test_file_path = uploads_dir / "p7_test.txt"
    test_file_path.write_bytes(b"phase 7 file repo test")

    try:
        record = FileRecord(
            filename="p7_test.txt",
            original_name="p7_orig.txt",
            file_path=str(test_file_path),
            file_type="text/plain",
            file_size_bytes=22,
            category="general",
            user_id=user_a.id,
        )
        db_session.add(record)
        db_session.commit()

        headers = {"Authorization": f"Bearer {token_a}"}
        res_list = client.get("/files", headers=headers)
        assert res_list.status_code == 200
        assert len(res_list.json()) >= 1

        res_dl = client.get(f"/files/{record.id}/download", headers=headers)
        assert res_dl.status_code == 200
        assert res_dl.content == b"phase 7 file repo test"

        res_del = client.delete(f"/files/{record.id}", headers=headers)
        assert res_del.status_code == 200
    finally:
        if test_file_path.exists():
            test_file_path.unlink()
