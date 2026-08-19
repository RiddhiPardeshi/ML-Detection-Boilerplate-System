from datetime import datetime, timezone
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.security import create_session_token, hash_password, verify_password
from ..models import User
from ..schemas.auth import ChangePasswordRequest, LoginRequest, ProfileUpdateRequest, RegisterRequest, UserResponse
from .audit import log_audit_event


class DuplicateUserError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidPasswordError(Exception):
    pass


def register_user(db: Session, request: RegisterRequest, source_ip: str | None = None) -> UserResponse:
    existing_user = db.scalar(
        select(User).where(
            or_(User.username == request.username, User.email == request.email)
        )
    )
    if existing_user is not None:
        raise DuplicateUserError("Username or email is already registered")

    user = User(
        username=request.username,
        email=request.email,
        password_hash=hash_password(request.password),
        last_login=datetime.now(timezone.utc),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise DuplicateUserError("Username or email is already registered") from error

    db.refresh(user)

    # Log audit event
    log_audit_event(
        db=db,
        action_category="Register",
        user_id=user.id,
        username=user.username,
        source_ip=source_ip,
        transaction_details=f"Account created for {user.username} ({user.email})"
    )

    token = create_session_token(user.id)
    response = UserResponse.model_validate(user)
    response.session_token = token
    return response


def authenticate_user(db: Session, request: LoginRequest, source_ip: str | None = None) -> UserResponse:
    identifier = request.email or request.username
    if not identifier:
        raise InvalidCredentialsError("Email or username is required")

    user = db.scalar(
        select(User).where(
            or_(User.email == identifier, User.username == identifier)
        )
    )

    if user is None or not verify_password(request.password, user.password_hash):
        log_audit_event(
            db=db,
            action_category="Login Failed",
            username=identifier,
            source_ip=source_ip,
            transaction_details=f"Failed login attempt for identifier '{identifier}'"
        )
        raise InvalidCredentialsError("Invalid email or password")

    if not user.is_active:
        log_audit_event(
            db=db,
            action_category="Login Failed",
            user_id=user.id,
            username=user.username,
            source_ip=source_ip,
            transaction_details="Login attempted on inactive account"
        )
        raise InvalidCredentialsError("Account is inactive")

    # Update last login timestamp
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    # Log audit event
    log_audit_event(
        db=db,
        action_category="Login Success",
        user_id=user.id,
        username=user.username,
        source_ip=source_ip,
        transaction_details=f"User {user.username} logged in successfully"
    )

    token = create_session_token(user.id)
    response = UserResponse.model_validate(user)
    response.session_token = token
    return response


def logout_user(db: Session, user: User, source_ip: str | None = None) -> None:
    log_audit_event(
        db=db,
        action_category="Logout",
        user_id=user.id,
        username=user.username,
        source_ip=source_ip,
        transaction_details=f"User {user.username} logged out"
    )


def update_user_profile(
    db: Session,
    user: User,
    request: ProfileUpdateRequest,
    source_ip: str | None = None,
) -> UserResponse:
    new_username = request.username.strip() if request.username else None
    new_email = request.email.strip().lower() if request.email else None

    if new_username and new_username != user.username:
        existing = db.scalar(select(User).where(User.username == new_username, User.id != user.id))
        if existing:
            raise DuplicateUserError("Username is already taken")
        user.username = new_username

    if new_email and new_email != user.email:
        if "@" not in new_email or "." not in new_email:
            raise ValueError("Invalid email address format")
        existing = db.scalar(select(User).where(User.email == new_email, User.id != user.id))
        if existing:
            raise DuplicateUserError("Email is already taken")
        user.email = new_email

    db.commit()
    db.refresh(user)

    log_audit_event(
        db=db,
        action_category="Profile Updated",
        user_id=user.id,
        username=user.username,
        source_ip=source_ip,
        transaction_details=f"User {user.username} updated profile details (email: {user.email})"
    )

    return UserResponse.model_validate(user)


def change_user_password(
    db: Session,
    user: User,
    request: ChangePasswordRequest,
    source_ip: str | None = None,
) -> UserResponse:
    if not verify_password(request.current_password, user.password_hash):
        log_audit_event(
            db=db,
            action_category="Password Change Failed",
            user_id=user.id,
            username=user.username,
            source_ip=source_ip,
            transaction_details="Password change attempt failed due to invalid current password"
        )
        raise InvalidPasswordError("Current password is incorrect")

    if request.new_password != request.confirm_new_password:
        raise ValueError("New passwords do not match")

    if len(request.new_password) < 6:
        raise ValueError("Password must be at least 6 characters long")

    user.password_hash = hash_password(request.new_password)
    db.commit()
    db.refresh(user)

    log_audit_event(
        db=db,
        action_category="Password Changed",
        user_id=user.id,
        username=user.username,
        source_ip=source_ip,
        transaction_details=f"User {user.username} changed password successfully"
    )

    token = create_session_token(user.id)
    response = UserResponse.model_validate(user)
    response.session_token = token
    return response
