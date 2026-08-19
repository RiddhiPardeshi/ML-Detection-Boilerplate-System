from fastapi import APIRouter

from .admin import admin_router
from .audit import audit_router
from .auth import auth_router
from .files import files_router
from .ml import ml_router


api_router = APIRouter()
api_router.include_router(admin_router)
api_router.include_router(audit_router)
api_router.include_router(auth_router)
api_router.include_router(files_router)
api_router.include_router(ml_router)


@api_router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
