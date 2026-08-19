from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..core.authorization import require_authenticated_user
from ..database import get_db
from ..ml.inference import predict, predict_proba
from ..ml.models import TabularModel, load_model
from ..models import AuditLog, Prediction, User, UserRole
from ..schemas.ml import (
    AuditItem,
    DashboardStatsResponse,
    ImageDetectionResponse,
    PredictionItem,
    PredictionRequest,
    PredictionResponse,
)
from ..services.audit import log_audit_event
from ..services.object_detection import run_object_detection
from ..services.predictions import save_prediction

ml_router = APIRouter(prefix="/ml", tags=["ml"])


def _to_json_value(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return _to_json_value(value.tolist())
    if isinstance(value, list):
        return [_to_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_json_value(item) for key, item in value.items()}
    return value


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"


@ml_router.post("/predict", response_model=PredictionResponse)
def predict_features(
    request: PredictionRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> PredictionResponse:
    settings = get_settings()
    try:
        model, preprocessor = load_model(Path(settings.ml_model_path))
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error

    features = pd.DataFrame([request.features])
    try:
        prediction = predict(model, features, preprocessor)
        probabilities = None
        if type(model).predict_proba is not TabularModel.predict_proba:
            probabilities = predict_proba(model, features, preprocessor)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference failed: {error}",
        ) from error

    prediction_value = _to_json_value(prediction)
    probability_value = _to_json_value(probabilities)
    current_user = getattr(http_request.state, "user", None)
    requesting_user = current_user if isinstance(current_user, User) else None
    try:
        save_prediction(
            db=db,
            prediction_value=prediction_value,
            probability=probability_value,
            model_identifier=settings.ml_model_identifier,
            model_version=settings.ml_model_version,
            user=requesting_user,
        )
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to persist prediction: {error}",
        ) from error

    # Log Predict Audit Event
    log_audit_event(
        db=db,
        action_category="Predict",
        user_id=requesting_user.id if requesting_user else None,
        username=requesting_user.username if requesting_user else "Anonymous",
        source_ip=_get_client_ip(http_request),
        transaction_details=f"Inference execution. Output={prediction_value}",
    )

    return PredictionResponse(prediction=prediction_value, probabilities=probability_value)


@ml_router.post("/detect", response_model=ImageDetectionResponse)
async def detect_objects_in_image(
    http_request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> ImageDetectionResponse:
    filename = file.filename or "uploaded_image.jpg"
    ext = Path(filename).suffix.lower()
    allowed_exts = {".png", ".jpg", ".jpeg", ".webp"}
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed formats: PNG, JPG, JPEG, WEBP.",
        )

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 10MB limit.",
        )

    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    try:
        result = run_object_detection(
            image_bytes=contents,
            original_filename=filename,
            upload_dir="uploads",
            confidence_threshold=0.3,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Object detection inference failed: {err}",
        )

    prob_summary = [d["confidence"] for d in result["detections"]] if result["detections"] else None

    saved_pred = save_prediction(
        db=db,
        prediction_value=result,
        probability=prob_summary,
        model_identifier=result["model_identifier"],
        model_version=result["model_version"],
        user=current_user,
    )

    # Save FileRecord entries for File Repository
    import os
    from ..models import FileRecord
    orig_filename = result["original_image_url"].replace("/uploads/", "")
    orig_path = os.path.join("uploads", orig_filename)
    orig_record = FileRecord(
        filename=orig_filename,
        original_name=filename,
        file_path=orig_path,
        file_type="image/jpeg",
        file_size_bytes=len(contents),
        category="original_image",
        user_id=current_user.id,
        prediction_id=saved_pred.id,
    )

    annotated_filename = result["annotated_image_url"].replace("/uploads/", "")
    annotated_path = os.path.join("uploads", annotated_filename)
    ann_size = os.path.getsize(annotated_path) if os.path.exists(annotated_path) else 0
    annotated_record = FileRecord(
        filename=annotated_filename,
        original_name=f"annotated_{filename}",
        file_path=annotated_path,
        file_type="image/jpeg",
        file_size_bytes=ann_size,
        category="annotated_image",
        user_id=current_user.id,
        prediction_id=saved_pred.id,
    )

    db.add_all([orig_record, annotated_record])
    db.commit()

    client_ip = _get_client_ip(http_request)
    log_audit_event(
        db=db,
        action_category="Predict",
        user_id=current_user.id,
        username=current_user.username,
        source_ip=client_ip,
        transaction_details=f"Image object detection executed. Objects detected={result['detection_count']}",
    )

    return ImageDetectionResponse(
        prediction_id=saved_pred.id,
        model_identifier=result["model_identifier"],
        model_version=result["model_version"],
        detection_count=result["detection_count"],
        detections=result["detections"],
        original_image_url=result["original_image_url"],
        annotated_image_url=result["annotated_image_url"],
        image_width=result["image_width"],
        image_height=result["image_height"],
        created_at=saved_pred.created_at,
    )


@ml_router.get("/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> DashboardStatsResponse:
    is_admin = current_user.role == UserRole.ADMIN

    pred_query = select(Prediction)
    if not is_admin:
        pred_query = pred_query.where(Prediction.user_id == current_user.id)

    predictions = db.scalars(pred_query.order_by(Prediction.created_at.desc())).all()
    total_inferences = len(predictions)

    summary: dict[str, int] = {}
    valid_confidences: list[float] = []

    for p in predictions:
        val = p.prediction_value
        if isinstance(val, dict) and "detections" in val:
            for det in val["detections"]:
                c_name = det.get("class_name", "unknown")
                summary[c_name] = summary.get(c_name, 0) + 1
                if "confidence" in det:
                    valid_confidences.append(float(det["confidence"]))
        else:
            val_str = str(val)
            summary[val_str] = summary.get(val_str, 0) + 1
            if isinstance(p.probability, list) and len(p.probability) > 0:
                if isinstance(p.probability[0], (int, float)):
                    valid_confidences.extend([float(v) for v in p.probability if isinstance(v, (int, float))])

    avg_conf = None
    if valid_confidences:
        avg_conf = round(sum(valid_confidences) / len(valid_confidences) * 100, 1)

    # Calculate real storage usage bytes from FileRecord database table
    from sqlalchemy import func
    from ..models import FileRecord
    storage_query = select(func.sum(FileRecord.file_size_bytes))
    if not is_admin:
        storage_query = storage_query.where(FileRecord.user_id == current_user.id)
    total_storage = db.scalar(storage_query)
    storage_bytes = int(total_storage) if total_storage is not None else None

    recent_preds = [
        PredictionItem(
            id=p.id,
            prediction_value=p.prediction_value,
            probability=p.probability,
            model_identifier=p.model_identifier,
            model_version=p.model_version,
            created_at=p.created_at,
        )
        for p in predictions[:5]
    ]

    audit_query = select(AuditLog)
    if not is_admin:
        audit_query = audit_query.where(
            or_(AuditLog.user_id == current_user.id, AuditLog.username == current_user.username)
        )
    audit_records = db.scalars(audit_query.order_by(AuditLog.timestamp.desc()).limit(5)).all()

    audit_timeline = [
        AuditItem(
            id=a.id,
            action_category=a.action_category,
            timestamp=a.timestamp,
            source_ip=a.source_ip,
            transaction_details=a.transaction_details,
        )
        for a in audit_records
    ]

    return DashboardStatsResponse(
        total_inferences=total_inferences,
        average_confidence=avg_conf,
        storage_bytes=storage_bytes,
        classification_summary=summary,
        recent_predictions=recent_preds,
        audit_timeline=audit_timeline,
    )
