from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from ..models import UserRole


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1)
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginRequest(BaseModel):
    email: str | None = None
    username: str | None = None
    password: str = Field(min_length=1)


class ProfileUpdateRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=150)
    email: str | None = Field(default=None, min_length=1, max_length=320)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)
    confirm_new_password: str = Field(min_length=6)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    is_active: bool
    role: UserRole
    created_at: datetime | None = None
    last_login: datetime | None = None
    session_token: str | None = None
