import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.security import create_session_token
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import AuditLog, Prediction, User, UserRole


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


def test_detect_requires_authentication():
    client = TestClient(app)
    response = client.post("/ml/detect", files={"file": ("test.png", b"fakebytes", "image/png")})
    assert response.status_code == 401


def test_detect_rejects_invalid_file_extension(db_session):
    user = User(
        username="testdetectuser",
        email="detect@example.com",
        password_hash="hashedpass",
        role=UserRole.USER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_session_token(user.id)

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)

    try:
        response = client.post(
            "/ml/detect",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("script.py", b"print('hello')", "text/x-python")},
        )
        assert response.status_code == 400
        assert "Unsupported file format" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_detect_executes_real_torchvision_inference(db_session):
    user = User(
        username="realuser",
        email="realuser@example.com",
        password_hash="hashedpass",
        role=UserRole.USER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_session_token(user.id)

    # Generate a real valid PNG image bytes using PIL
    img = Image.new("RGB", (320, 320), color="blue")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_bytes = img_byte_arr.getvalue()

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)

    try:
        response = client.post(
            "/ml/detect",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("sample_image.png", img_bytes, "image/png")},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["model_identifier"] == "ssdlite320_mobilenet_v3_large"
        assert "detection_count" in data
        assert "detections" in data
        assert "original_image_url" in data
        assert "annotated_image_url" in data
        assert data["original_image_url"].startswith("/uploads/")
        assert data["annotated_image_url"].startswith("/uploads/")

        # Verify prediction record in DB
        preds = db_session.query(Prediction).all()
        assert len(preds) == 1
        assert preds[0].user_id == user.id
        assert preds[0].model_identifier == "ssdlite320_mobilenet_v3_large"

        # Verify audit log in DB
        audit_logs = db_session.query(AuditLog).filter(AuditLog.action_category == "Predict").all()
        assert len(audit_logs) >= 1
        assert audit_logs[-1].user_id == user.id
    finally:
        app.dependency_overrides.clear()
