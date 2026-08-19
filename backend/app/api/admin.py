from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.authorization import require_admin
from ..database import get_db
from ..models import User
from ..schemas.admin import AdminUserResponse, RoleUpdateRequest
from ..services.admin import (
    UserNotFoundError,
    change_user_role,
    get_user,
    list_users,
    set_user_active,
)


admin_router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@admin_router.get("", response_model=list[AdminUserResponse])
def list_all_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[User]:
    return list_users(db)


@admin_router.get("/{user_id}", response_model=AdminUserResponse)
def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> User:
    try:
        return get_user(db, user_id)
    except UserNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@admin_router.patch("/{user_id}/activate", response_model=AdminUserResponse)
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> User:
    try:
        return set_user_active(db, user_id, True)
    except UserNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@admin_router.patch("/{user_id}/deactivate", response_model=AdminUserResponse)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> User:
    try:
        return set_user_active(db, user_id, False)
    except UserNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@admin_router.patch("/{user_id}/role", response_model=AdminUserResponse)
def update_user_role(
    user_id: int,
    request: RoleUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> User:
    try:
        return change_user_role(db, user_id, request.role)
    except UserNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
