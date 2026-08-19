from fastapi.testclient import TestClient

from backend.app.api import ml as ml_api
from backend.app.database import get_db
from backend.app.main import app


def _empty_db():
    yield object()


def test_health_endpoint():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_prediction_request_validation():
    app.dependency_overrides[get_db] = _empty_db
    try:
        response = TestClient(app).post("/ml/predict", json={})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_prediction_missing_model_artifact_returns_500(monkeypatch):
    def missing_artifact(path):
        raise FileNotFoundError("Model artifact not found: missing.joblib")

    monkeypatch.setattr(ml_api, "load_model", missing_artifact)
    app.dependency_overrides[get_db] = _empty_db
    try:
        response = TestClient(app).post(
            "/ml/predict",
            json={"features": {"value": 1}},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert "Model artifact not found" in response.json()["detail"]
