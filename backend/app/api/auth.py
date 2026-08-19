from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from ..core.authorization import require_authenticated_user
from ..database import get_db
from ..models import User
from ..schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    UserResponse,
)
from ..services.auth import (
    DuplicateUserError,
    InvalidCredentialsError,
    InvalidPasswordError,
    authenticate_user,
    change_user_password,
    logout_user,
    register_user,
    update_user_profile,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"


@auth_router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: RegisterRequest,
    http_request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> UserResponse:
    try:
        user_resp = register_user(db, request, source_ip=_get_client_ip(http_request))
        if user_resp.session_token:
            response.set_cookie("session_token", user_resp.session_token, httponly=True, samesite="lax")
        return user_resp
    except DuplicateUserError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@auth_router.post("/login", response_model=UserResponse)
def login(
    request: LoginRequest,
    http_request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> UserResponse:
    try:
        user_resp = authenticate_user(db, request, source_ip=_get_client_ip(http_request))
        if user_resp.session_token:
            response.set_cookie("session_token", user_resp.session_token, httponly=True, samesite="lax")
        return user_resp
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error


@auth_router.post("/logout")
def logout(
    http_request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> dict[str, str]:
    logout_user(db, current_user, source_ip=_get_client_ip(http_request))
    response.delete_cookie("session_token")
    return {"message": "Logged out successfully"}


@auth_router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(require_authenticated_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@auth_router.put("/profile", response_model=UserResponse)
def update_profile(
    request: ProfileUpdateRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> UserResponse:
    try:
        return update_user_profile(db, current_user, request, source_ip=_get_client_ip(http_request))
    except DuplicateUserError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@auth_router.post("/change-password", response_model=UserResponse)
def change_password(
    request: ChangePasswordRequest,
    http_request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> UserResponse:
    try:
        user_resp = change_user_password(db, current_user, request, source_ip=_get_client_ip(http_request))
        if user_resp.session_token:
            response.set_cookie("session_token", user_resp.session_token, httponly=True, samesite="lax")
        return user_resp
    except InvalidPasswordError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
