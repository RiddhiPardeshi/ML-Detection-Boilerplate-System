from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class PredictionRequest(BaseModel):
    features: dict[str, Any] = Field(min_length=1)


class PredictionResponse(BaseModel):
    prediction: Any
    probabilities: Any | None = None


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class DetectionItem(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox


class ImageDetectionResponse(BaseModel):
    prediction_id: int
    model_identifier: str
    model_version: str
    detection_count: int
    detections: list[DetectionItem]
    original_image_url: str
    annotated_image_url: str
    image_width: int
    image_height: int
    created_at: datetime


class PredictionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prediction_value: Any
    probability: Any | None = None
    model_identifier: str
    model_version: str
    created_at: datetime


class AuditItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action_category: str
    timestamp: datetime
    source_ip: str | None = None
    transaction_details: str | None = None


class DashboardStatsResponse(BaseModel):
    total_inferences: int
    average_confidence: float | None = None
    storage_bytes: int | None = None
    classification_summary: dict[str, int]
    recent_predictions: list[PredictionItem]
    audit_timeline: list[AuditItem]
