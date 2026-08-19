from datetime import datetime
from pydantic import BaseModel, ConfigDict


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    original_name: str
    file_type: str
    file_size_bytes: int
    category: str
    user_id: int
    prediction_id: int | None = None
    created_at: datetime
    download_url: str
