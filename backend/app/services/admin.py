from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import User, UserRole


class UserNotFoundError(Exception):
    pass


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)).all())


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError("User not found")
    return user


def set_user_active(db: Session, user_id: int, is_active: bool) -> User:
    user = get_user(db, user_id)
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


def change_user_role(db: Session, user_id: int, role: UserRole) -> User:
    user = get_user(db, user_id)
    user.role = role
    db.commit()
    db.refresh(user)
    return user
