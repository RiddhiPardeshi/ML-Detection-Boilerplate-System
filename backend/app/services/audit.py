from datetime import datetime
from sqlalchemy.orm import Session

from ..models import AuditLog


def log_audit_event(
    db: Session,
    action_category: str,
    user_id: int | None = None,
    username: str | None = None,
    source_ip: str | None = None,
    transaction_details: str | None = None,
) -> AuditLog:
    """Record an audit log entry in the database."""
    log_entry = AuditLog(
        user_id=user_id,
        username=username,
        action_category=action_category,
        source_ip=source_ip or "127.0.0.1",
        transaction_details=transaction_details,
    )
    db.add(log_entry)
    try:
        db.commit()
        db.refresh(log_entry)
    except Exception as error:
        db.rollback()
        # Fallback print if DB save fails
        print(f"[AuditLog Error] Could not save audit log: {error}")
    return log_entry
