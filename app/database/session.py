from collections.abc import AsyncGenerator
import logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

def _create_engine_instance():
    url = settings.database_url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if "postgresql" in url:
        import socket
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(url.replace("+asyncpg", ""))
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 5432
            timeout = 1.0 if host in ("127.0.0.1", "localhost") else 3.0
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            if result != 0:
                logger.warning(f"PostgreSQL on {host}:{port} unreachable, falling back to SQLite.")
                url = "sqlite+aiosqlite:///./dashboard.db"
        except Exception as e:
            logger.warning(f"Error checking PostgreSQL ({e}), falling back to SQLite.")
            url = "sqlite+aiosqlite:///./dashboard.db"

    return create_async_engine(url, echo=False)


engine = _create_engine_instance()

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

