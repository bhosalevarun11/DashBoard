import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from app.core.limiter import limiter
    HAS_SLOWAPI = limiter is not None
except Exception:
    limiter = None
    HAS_SLOWAPI = False

from sqlalchemy import text

import app.models
from app.api import analytics, auth, data, reports_custom
from app.core.config import get_settings
from app.database.base import Base
from app.database.session import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard.security")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        settings = get_settings()
        is_prod = settings.app_env.lower() == "production"

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; img-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
        
        if is_prod:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


async def _migrate_columns(conn):
    await conn.run_sync(Base.metadata.create_all)
    try:
        await conn.execute(text("ALTER TABLE orders ADD COLUMN payment_fee FLOAT DEFAULT 0;"))
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    try:
        async with engine.begin() as conn:
            await _migrate_columns(conn)
    except Exception as e:
        logger.warning(f"PostgreSQL connection failed during startup ({e}). Falling back to SQLite database.")
        from app.database import session as db_session
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        sqlite_engine = create_async_engine("sqlite+aiosqlite:///./dashboard.db", echo=False)
        db_session.engine = sqlite_engine
        db_session.AsyncSessionLocal = async_sessionmaker(sqlite_engine, class_=AsyncSession, expire_on_commit=False)
        async with sqlite_engine.begin() as conn:
            await _migrate_columns(conn)

    # Auto-initialize admin user, business and sample data if new deployment
    try:
        from app.database.session import AsyncSessionLocal
        from app.models import User, UserRole, Business, Order
        from sqlalchemy import select
        async with AsyncSessionLocal() as session:
            usr = (await session.execute(select(User).where(User.email == "bhosalevarun1910@gmail.com"))).scalar_one_or_none()
            if not usr:
                usr = User(
                    id=1,
                    name="Varun Bhosale",
                    email="bhosalevarun1910@gmail.com",
                    password_hash="$pbkdf2-sha256$29000$5jwHIOTcey9lzBmjFKL0Hg$jRPzX96lV765gdsLnJUqfJ1EN5NMIPxaNpSnnmtyhUM",
                    role=UserRole.admin,
                )
                session.add(usr)
                await session.flush()
            biz = (await session.execute(select(Business).where(Business.id == 1))).scalar_one_or_none()
            if not biz:
                biz = Business(id=1, user_id=usr.id, name="VBCreations", currency="INR", timezone="Asia/Kolkata")
                session.add(biz)
                await session.flush()
            has_orders = (await session.execute(select(Order.id).where(Order.business_id == 1).limit(1))).scalar_one_or_none()
            if not has_orders:
                from app.seed_demo_data import seed_365d_store_data
                await seed_365d_store_data(session, business_id=1, seed_value=42, reset_first=False)
            await session.commit()
    except Exception as init_err:
        logger.warning(f"Auto-initialization notice: {init_err}")

    yield
    try:
        await engine.dispose()
    except Exception:
        pass


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=r"^https://.*\.github\.io.*$|^https://.*\.onrender\.com.*$|^http://localhost(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    if HAS_SLOWAPI and limiter:
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers,
            )
        req_id = uuid.uuid4().hex
        logger.error(f"Unhandled Exception [req_id={req_id}] on {request.method} {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred.", "request_id": req_id},
        )

    app.include_router(auth.router, prefix="/api")
    app.include_router(data.router, prefix="/api")
    app.include_router(analytics.router, prefix="/api")
    app.include_router(reports_custom.router, prefix="/api")

    @app.get("/health")
    async def health():
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "dashboard"}

    return app


app = create_app()
