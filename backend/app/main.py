from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text

from .api import api_router
from .config import get_settings
from .core.security import decode_session_token
from .database import Base, get_db, engine
from .models import User


def init_db():
    """Safely create tables and add missing columns without dropping any data."""
    Base.metadata.create_all(bind=engine)
    database_url = get_settings().database_url.lower()
    if "sqlite" in database_url:
        with engine.connect() as conn:
            try:
                columns = [row[1] for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()]
                if columns and "last_login" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN last_login DATETIME"))
                    conn.commit()
            except Exception as error:
                print(f"[DB Init] Info: {error}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)


@app.middleware("http")
async def authenticate_session_middleware(request: Request, call_next):
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        request.state.client_ip = forwarded.split(",")[0].strip()
    elif request.client:
        request.state.client_ip = request.client.host
    else:
        request.state.client_ip = "127.0.0.1"

    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif auth_header and auth_header.startswith("Session "):
        token = auth_header[8:].strip()
    else:
        token = request.cookies.get("session_token")

    if token:
        user_id = decode_session_token(token)
        if user_id:
            get_db_fn = request.app.dependency_overrides.get(get_db, get_db)
            db_gen = get_db_fn()
            db = next(db_gen)
            try:
                user = db.scalar(select(User).where(User.id == user_id, User.is_active == True))
                if user:
                    request.state.user = user
                    request.state.session_token = token
            except Exception:
                pass
            finally:
                try:
                    next(db_gen)
                except StopIteration:
                    pass

    response = await call_next(request)
    return response


app.include_router(api_router)

uploads_directory = Path(__file__).resolve().parents[2] / "uploads"
uploads_directory.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_directory), name="uploads")

frontend_directory = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/static", StaticFiles(directory=frontend_directory), name="static")
app.mount("/", StaticFiles(directory=frontend_directory, html=True), name="frontend")
