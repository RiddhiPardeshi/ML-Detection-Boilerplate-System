from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .file_record import FileRecord
    from .user import User


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prediction_value: Mapped[Any] = mapped_column(JSON, nullable=False)
    probability: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    model_identifier: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User | None"] = relationship(back_populates="predictions")
    files: Mapped[list["FileRecord"]] = relationship(back_populates="prediction")
