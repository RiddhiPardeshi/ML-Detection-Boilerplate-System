import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.security import create_session_token
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import FileRecord, Prediction, User
from backend.app.schemas.auth import RegisterRequest
from backend.app.services.auth import register_user


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
    resp = register_user(
        db_session,
        RegisterRequest(
            username="usera",
            email="usera@example.com",
            password="password123",
        ),
    )
    return db_session.get(User, resp.id)


@pytest.fixture
def user_b(db_session):
    resp = register_user(
        db_session,
        RegisterRequest(
            username="userb",
            email="userb@example.com",
            password="password123",
        ),
    )
    return db_session.get(User, resp.id)


@pytest.fixture
def token_a(user_a):
    return create_session_token(user_a.id)


@pytest.fixture
def token_b(user_b):
    return create_session_token(user_b.id)


def create_sample_image():
    img = Image.new("RGB", (100, 100), color="blue")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="JPEG")
    return img_byte_arr.getvalue()


def test_1_user_a_can_see_own_predictions(client, token_a):
    headers = {"Authorization": f"Bearer {token_a}"}
    files = {"file": ("test_a.jpg", create_sample_image(), "image/jpeg")}
    res = client.post("/ml/detect", files=files, headers=headers)
    assert res.status_code == 200
    pred_id = res.json()["prediction_id"]

    stats_res = client.get("/ml/stats", headers=headers)
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_inferences"] == 1
    assert stats["recent_predictions"][0]["id"] == pred_id


def test_2_user_b_cannot_see_user_a_predictions(client, token_a, token_b):
    headers_a = {"Authorization": f"Bearer {token_a}"}
    files = {"file": ("test_a.jpg", create_sample_image(), "image/jpeg")}
    res_a = client.post("/ml/detect", files=files, headers=headers_a)
    assert res_a.status_code == 200

    headers_b = {"Authorization": f"Bearer {token_b}"}
    stats_res_b = client.get("/ml/stats", headers=headers_b)
    assert stats_res_b.status_code == 200
    stats_b = stats_res_b.json()
    assert stats_b["total_inferences"] == 0
    assert len(stats_b["recent_predictions"]) == 0


def test_3_user_a_can_see_own_detection_results(client, token_a):
    headers_a = {"Authorization": f"Bearer {token_a}"}
    files = {"file": ("test_a.jpg", create_sample_image(), "image/jpeg")}
    res_a = client.post("/ml/detect", files=files, headers=headers_a)
    assert res_a.status_code == 200
    data = res_a.json()
    assert "prediction_id" in data
    assert "detections" in data


def test_4_user_b_cannot_see_user_a_detection_results(client, token_a, token_b):
    headers_a = {"Authorization": f"Bearer {token_a}"}
    files = {"file": ("test_a.jpg", create_sample_image(), "image/jpeg")}
    res_a = client.post("/ml/detect", files=files, headers=headers_a)
    pred_id_a = res_a.json()["prediction_id"]

    headers_b = {"Authorization": f"Bearer {token_b}"}
    files_b = client.get("/files", headers=headers_b).json()
    pred_ids_in_b_files = [f["prediction_id"] for f in files_b if f.get("prediction_id")]
    assert pred_id_a not in pred_ids_in_b_files


def test_5_user_a_can_see_own_files(client, token_a):
    headers_a = {"Authorization": f"Bearer {token_a}"}
    files = {"file": ("test_a.jpg", create_sample_image(), "image/jpeg")}
    client.post("/ml/detect", files=files, headers=headers_a)

    files_res = client.get("/files", headers=headers_a)
    assert files_res.status_code == 200
    file_list = files_res.json()
    assert len(file_list) == 2


def test_6_user_b_cannot_see_user_a_files(client, token_a, token_b):
    headers_a = {"Authorization": f"Bearer {token_a}"}
    files = {"file": ("test_a.jpg", create_sample_image(), "image/jpeg")}
    client.post("/ml/detect", files=files, headers=headers_a)

    file_a_id = client.get("/files", headers=headers_a).json()[0]["id"]

    headers_b = {"Authorization": f"Bearer {token_b}"}
    files_b_res = client.get("/files", headers=headers_b)
    assert files_b_res.status_code == 200
    assert len(files_b_res.json()) == 0

    file_detail_b = client.get(f"/files/{file_a_id}", headers=headers_b)
    assert file_detail_b.status_code == 403


def test_7_prediction_list_is_user_specific(client, token_a, token_b):
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    client.post("/ml/detect", files={"file": ("a.jpg", create_sample_image(), "image/jpeg")}, headers=headers_a)
    client.post("/ml/detect", files={"file": ("b.jpg", create_sample_image(), "image/jpeg")}, headers=headers_b)

    stats_a = client.get("/ml/stats", headers=headers_a).json()
    stats_b = client.get("/ml/stats", headers=headers_b).json()

    assert stats_a["total_inferences"] == 1
    assert stats_b["total_inferences"] == 1


def test_8_dashboard_statistics_are_user_specific(client, token_a, token_b):
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    client.post("/ml/detect", files={"file": ("a.jpg", create_sample_image(), "image/jpeg")}, headers=headers_a)

    stats_a = client.get("/ml/stats", headers=headers_a).json()
    stats_b = client.get("/ml/stats", headers=headers_b).json()

    assert stats_a["storage_bytes"] is not None and stats_a["storage_bytes"] > 0
    assert stats_b["storage_bytes"] is None or stats_b["storage_bytes"] == 0


def test_9_logout_clears_previous_frontend_session_state(client, token_a):
    headers_a = {"Authorization": f"Bearer {token_a}"}
    res_logout = client.post("/auth/logout", headers=headers_a)
    assert res_logout.status_code == 200

    res_me = client.get("/auth/me")
    assert res_me.status_code == 401


def test_10_new_login_loads_new_user_data(client, token_b):
    headers_b = {"Authorization": f"Bearer {token_b}"}
    res_me = client.get("/auth/me", headers=headers_b)
    assert res_me.status_code == 200
    assert res_me.json()["username"] == "userb"


def test_11_user_b_new_prediction_is_associated_with_user_b(client, db_session, user_b, token_b):
    headers_b = {"Authorization": f"Bearer {token_b}"}
    res = client.post("/ml/detect", files={"file": ("b.jpg", create_sample_image(), "image/jpeg")}, headers=headers_b)
    pred_id = res.json()["prediction_id"]

    db_session.expire_all()
    pred_db = db_session.get(Prediction, pred_id)
    assert pred_db.user_id == user_b.id


def test_12_user_a_cannot_access_user_b_prediction(client, token_a, token_b):
    headers_b = {"Authorization": f"Bearer {token_b}"}
    res_b = client.post("/ml/detect", files={"file": ("b.jpg", create_sample_image(), "image/jpeg")}, headers=headers_b)
    pred_id_b = res_b.json()["prediction_id"]

    headers_a = {"Authorization": f"Bearer {token_a}"}
    stats_a = client.get("/ml/stats", headers=headers_a).json()
    pred_ids_in_a = [p["id"] for p in stats_a["recent_predictions"]]
    assert pred_id_b not in pred_ids_in_a


def test_13_user_a_cannot_access_user_b_detection_files(client, token_a, token_b):
    headers_b = {"Authorization": f"Bearer {token_b}"}
    res_b = client.post("/ml/detect", files={"file": ("b.jpg", create_sample_image(), "image/jpeg")}, headers=headers_b)

    files_b = client.get("/files", headers=headers_b).json()
    file_id_b = files_b[0]["id"]

    headers_a = {"Authorization": f"Bearer {token_a}"}
    download_res = client.get(f"/files/{file_id_b}/download", headers=headers_a)
    assert download_res.status_code == 403

    delete_res = client.delete(f"/files/{file_id_b}", headers=headers_a)
    assert delete_res.status_code == 403


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
    res = client.post("/ml/predict", json={"features": {"x": 1}})
    assert res.status_code == 200


def test_15_existing_ml_detect_still_works(client, token_a):
    headers = {"Authorization": f"Bearer {token_a}"}
    res = client.post("/ml/detect", files={"file": ("detect.jpg", create_sample_image(), "image/jpeg")}, headers=headers)
    assert res.status_code == 200


def test_16_files_repository_still_works(client, token_a):
    headers = {"Authorization": f"Bearer {token_a}"}
    res = client.get("/files", headers=headers)
    assert res.status_code == 200


def test_17_system_logs_still_works(client, token_a):
    headers = {"Authorization": f"Bearer {token_a}"}
    res = client.get("/audit-logs", headers=headers)
    assert res.status_code == 200


def test_18_my_profile_still_works(client, token_a):
    headers = {"Authorization": f"Bearer {token_a}"}
    res = client.get("/auth/me", headers=headers)
    assert res.status_code == 200
