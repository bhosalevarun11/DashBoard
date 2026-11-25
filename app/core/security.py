import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")
ALGORITHM = "HS256"

# Pre-computed dummy hash to ensure constant-time response for non-existent users
DUMMY_HASH = pwd_context.hash("dummy_password_for_timing_mitigation_1234567890")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password[:72], hashed_password)


def verify_dummy_password(plain_password: str) -> bool:
    pwd_context.verify(plain_password[:72], DUMMY_HASH)
    return False


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password[:72])


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(subject: str, expires_delta: timedelta | None = None, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=15)
    )
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire, "type": "access", "jti": uuid.uuid4().hex}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(subject: str, family_id: str | None = None) -> tuple[str, str, datetime]:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    fid = family_id or uuid.uuid4().hex
    jti = uuid.uuid4().hex
    payload = {"sub": str(subject), "exp": expire, "type": "refresh", "family_id": fid, "jti": jti}
    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return token, fid, expire


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
