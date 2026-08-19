from fastapi import HTTPException, Request, status

from ..models import User, UserRole


def get_current_user(request: Request) -> User:
    current_user = getattr(request.state, "user", None)
    if not isinstance(current_user, User):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return current_user


def require_authenticated_user(request: Request) -> User:
    return get_current_user(request)


def require_admin(request: Request) -> User:
    current_user = get_current_user(request)
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user
