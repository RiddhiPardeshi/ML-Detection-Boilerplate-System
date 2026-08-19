from pydantic import BaseModel, ConfigDict

from ..models import UserRole


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    is_active: bool
    role: UserRole


class RoleUpdateRequest(BaseModel):
    role: UserRole
