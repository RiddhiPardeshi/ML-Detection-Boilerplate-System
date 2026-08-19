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
from backend.app.models import FileRecord, Prediction, User, UserRole


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
    user = User(
        username="fileuser",
        email="fileuser@example.com",
        password_hash="hashedpass",
        role=UserRole.USER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def other_user(db_session):
    user = User(
        username="otheruser",
        email="other@example.com",
        password_hash="hashedpass",
        role=UserRole.USER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_token(test_user):
    return create_session_token(test_user.id)


@pytest.fixture
def other_token(other_user):
    return create_session_token(other_user.id)


def test_1_unauthenticated_access_rejected(client):
    res1 = client.get("/files")
    assert res1.status_code == 401

    res2 = client.get("/files/1")
    assert res2.status_code == 401

    res3 = client.get("/files/1/download")
    assert res3.status_code == 401

    res4 = client.delete("/files/1")
    assert res4.status_code == 401


def test_2_authenticated_user_can_list_own_files(client, db_session, test_user, user_token):
    record = FileRecord(
        filename="test_file.jpg",
        original_name="my_photo.jpg",
        file_path="uploads/test_file.jpg",
        file_type="image/jpeg",
        file_size_bytes=1024,
        category="original_image",
        user_id=test_user.id,
    )
    db_session.add(record)
    db_session.commit()

    res = client.get("/files", headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 200
    files = res.json()
    assert len(files) == 1
    assert files[0]["filename"] == "test_file.jpg"
    assert files[0]["original_name"] == "my_photo.jpg"


def test_3_user_cannot_access_another_user_file(client, db_session, test_user, other_token):
    record = FileRecord(
        filename="user_a_file.jpg",
        original_name="user_a.jpg",
        file_path="uploads/user_a_file.jpg",
        file_type="image/jpeg",
        file_size_bytes=2048,
        category="original_image",
        user_id=test_user.id,
    )
    db_session.add(record)
    db_session.commit()

    headers = {"Authorization": f"Bearer {other_token}"}
    res_get = client.get(f"/files/{record.id}", headers=headers)
    assert res_get.status_code == 403

    res_dl = client.get(f"/files/{record.id}/download", headers=headers)
    assert res_dl.status_code == 403


def test_4_file_metadata_is_correct(client, db_session, test_user, user_token):
    pred = Prediction(
        prediction_value={"status": "ok"},
        model_identifier="test-model",
        model_version="1.0",
        user=test_user,
    )
    db_session.add(pred)
    db_session.commit()

    record = FileRecord(
        filename="meta_file.jpg",
        original_name="meta_orig.jpg",
        file_path="uploads/meta_file.jpg",
        file_type="image/jpeg",
        file_size_bytes=4096,
        category="annotated_image",
        user_id=test_user.id,
        prediction_id=pred.id,
    )
    db_session.add(record)
    db_session.commit()

    res = client.get(f"/files/{record.id}", headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == record.id
    assert data["filename"] == "meta_file.jpg"
    assert data["original_name"] == "meta_orig.jpg"
    assert data["file_type"] == "image/jpeg"
    assert data["file_size_bytes"] == 4096
    assert data["category"] == "annotated_image"
    assert data["user_id"] == test_user.id
    assert data["prediction_id"] == pred.id
    assert data["download_url"] == f"/files/{record.id}/download"
    assert "file_path" not in data


def test_5_download_works(client, db_session, test_user, user_token):
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    test_file_path = uploads_dir / "dl_test.txt"
    test_file_path.write_bytes(b"hello world download test")

    try:
        record = FileRecord(
            filename="dl_test.txt",
            original_name="download_me.txt",
            file_path=str(test_file_path),
            file_type="text/plain",
            file_size_bytes=25,
            category="general",
            user_id=test_user.id,
        )
        db_session.add(record)
        db_session.commit()

        res = client.get(f"/files/{record.id}/download", headers={"Authorization": f"Bearer {user_token}"})
        assert res.status_code == 200
        assert res.content == b"hello world download test"
    finally:
        if test_file_path.exists():
            test_file_path.unlink()


def test_6_delete_works(client, db_session, test_user, user_token):
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    test_file_path = uploads_dir / "del_test.txt"
    test_file_path.write_bytes(b"content to delete")

    record = FileRecord(
        filename="del_test.txt",
        original_name="delete_me.txt",
        file_path=str(test_file_path),
        file_type="text/plain",
        file_size_bytes=17,
        category="general",
        user_id=test_user.id,
    )
    db_session.add(record)
    db_session.commit()
    file_id = record.id

    res = client.delete(f"/files/{file_id}", headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 200
    assert not test_file_path.exists()

    db_session.expire_all()
    deleted_rec = db_session.get(FileRecord, file_id)
    assert deleted_rec is None


def test_7_unauthorized_delete_rejected(client, db_session, test_user, other_token):
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    test_file_path = uploads_dir / "protected.txt"
    test_file_path.write_bytes(b"protected content")

    try:
        record = FileRecord(
            filename="protected.txt",
            original_name="protected.txt",
            file_path=str(test_file_path),
            file_type="text/plain",
            file_size_bytes=17,
            category="general",
            user_id=test_user.id,
        )
        db_session.add(record)
        db_session.commit()

        res = client.delete(f"/files/{record.id}", headers={"Authorization": f"Bearer {other_token}"})
        assert res.status_code == 403
        assert test_file_path.exists()
    finally:
        if test_file_path.exists():
            test_file_path.unlink()


def test_8_path_traversal_rejected(client, db_session, test_user, user_token):
    record = FileRecord(
        filename="traversal.txt",
        original_name="traversal.txt",
        file_path="uploads/../../etc/passwd",
        file_type="text/plain",
        file_size_bytes=100,
        category="general",
        user_id=test_user.id,
    )
    db_session.add(record)
    db_session.commit()

    res = client.get(f"/files/{record.id}/download", headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 400
    assert "security violation" in res.json()["detail"].lower()


def test_9_empty_repository_handled_correctly(client, user_token):
    res = client.get("/files", headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 200
    assert res.json() == []


def test_10_existing_ml_detect_still_works(client, db_session, test_user, user_token):
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="red")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="JPEG")
    img_bytes = img_byte_arr.getvalue()

    files = {"file": ("test_detect.jpg", img_bytes, "image/jpeg")}
    headers = {"Authorization": f"Bearer {user_token}"}

    res = client.post("/ml/detect", files=files, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "prediction_id" in data
    assert "original_image_url" in data
    assert "annotated_image_url" in data

    # Verify FileRecord entries created
    records = db_session.query(FileRecord).filter_by(user_id=test_user.id).all()
    assert len(records) >= 2


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
    data = res.json()
    assert "prediction" in data


