from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..core.authorization import require_authenticated_user
from ..database import get_db
from ..models import AuditLog, User, UserRole
from ..schemas.audit_log import AuditLogResponse, PaginatedAuditLogResponse

audit_router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@audit_router.get("", response_model=PaginatedAuditLogResponse)
def list_audit_logs(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    action: Optional[str] = Query(default=None),
    username: Optional[str] = Query(default=None),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> PaginatedAuditLogResponse:
    query = select(AuditLog)

    # User isolation: Non-admin users see ONLY their own logs
    if current_user.role != UserRole.ADMIN:
        query = query.where(
            or_(
                AuditLog.user_id == current_user.id,
                AuditLog.username == current_user.username,
            )
        )
    elif username:
        query = query.where(AuditLog.username.ilike(f"%{username.strip()}%"))

    if action and action.strip():
        query = query.where(AuditLog.action_category.ilike(f"%{action.strip()}%"))

    if start_date:
        query = query.where(AuditLog.timestamp >= start_date)

    if end_date:
        # If time is 00:00:00, extend end_date to end of the day
        if end_date.hour == 0 and end_date.minute == 0 and end_date.second == 0:
            end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        query = query.where(AuditLog.timestamp <= end_date)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    pages = (total + limit - 1) // limit if total > 0 else 1

    records = db.scalars(
        query.order_by(AuditLog.timestamp.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    items = [AuditLogResponse.model_validate(r) for r in records]

    return PaginatedAuditLogResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )
