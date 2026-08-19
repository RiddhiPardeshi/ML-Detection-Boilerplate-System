from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    username: str | None = None
    timestamp: datetime
    action_category: str
    source_ip: str | None = None
    transaction_details: str | None = None


class PaginatedAuditLogResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    limit: int
    pages: int
