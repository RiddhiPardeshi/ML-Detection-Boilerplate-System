import os
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse as FastAPIFileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.authorization import require_authenticated_user
from ..database import get_db
from ..models import FileRecord, User, UserRole
from ..schemas.file_record import FileResponse

files_router = APIRouter(prefix="/files", tags=["files"])


def _to_file_response(record: FileRecord) -> FileResponse:
    return FileResponse(
        id=record.id,
        filename=record.filename,
        original_name=record.original_name,
        file_type=record.file_type,
        file_size_bytes=record.file_size_bytes,
        category=record.category,
        user_id=record.user_id,
        prediction_id=record.prediction_id,
        created_at=record.created_at,
        download_url=f"/files/{record.id}/download",
    )


@files_router.get("", response_model=List[FileResponse])
def list_user_files(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> List[FileResponse]:
    query = select(FileRecord)
    if current_user.role != UserRole.ADMIN:
        query = query.where(FileRecord.user_id == current_user.id)
    records = db.scalars(query.order_by(FileRecord.created_at.desc())).all()
    return [_to_file_response(r) for r in records]


@files_router.get("/{file_id}", response_model=FileResponse)
def get_file_detail(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> FileResponse:
    record = db.scalar(select(FileRecord).where(FileRecord.id == file_id))
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File #{file_id} not found.",
        )
    if current_user.role != UserRole.ADMIN and record.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    return _to_file_response(record)


@files_router.get("/{file_id}/download")
def download_file(
    file_id: int,
    disposition: str = "attachment",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    record = db.scalar(select(FileRecord).where(FileRecord.id == file_id))
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File #{file_id} not found.",
        )
    if current_user.role != UserRole.ADMIN and record.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

    base_dir = Path("uploads").resolve()
    target_path = Path(record.file_path).resolve()

    try:
        if not target_path.is_relative_to(base_dir):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file path security violation.",
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path security violation.",
        )

    if not target_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File content does not exist on disk.",
        )

    disp_type = "inline" if disposition == "inline" else "attachment"

    return FastAPIFileResponse(
        path=str(target_path),
        filename=record.original_name if disp_type == "attachment" else None,
        media_type=record.file_type,
        content_disposition_type=disp_type,
    )


@files_router.delete("/{file_id}")
def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    record = db.scalar(select(FileRecord).where(FileRecord.id == file_id))
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File #{file_id} not found.",
        )
    if current_user.role != UserRole.ADMIN and record.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

    # Safely delete file from disk if it exists and is under base_dir
    base_dir = Path("uploads").resolve()
    target_path = Path(record.file_path).resolve()
    try:
        if target_path.is_relative_to(base_dir) and target_path.exists():
            target_path.unlink()
    except (ValueError, Exception):
        pass

    db.delete(record)
    db.commit()

    return {"detail": f"File #{file_id} deleted successfully."}

