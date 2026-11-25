from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user, require_roles
from app.core.limiter import rate_limit
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    hash_token,
    verify_dummy_password,
    verify_password,
)
from app.database.session import get_db
from app.models import Business, RefreshToken, User, UserRole
from app.schemas import BusinessCreate, BusinessResponse, TokenResponse, UserCreate, UserLogin, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, refresh_token_str: str) -> None:
    settings = get_settings()
    is_prod = settings.app_env.lower() == "production"
    response.set_cookie(
        key="refreshToken",
        value=refresh_token_str,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        path="/",
        max_age=settings.refresh_token_expire_days * 86400,
    )
    response.headers["Cache-Control"] = "no-store"


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key="refreshToken", path="/")
    response.headers["Cache-Control"] = "no-store"


@router.post("/register", response_model=TokenResponse)
@rate_limit("5/minute")
async def register(
    request: Request,
    response: Response,
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    clean_email = payload.email.lower().strip()
    existing = await db.execute(select(User).where(func.lower(User.email) == clean_email))
    if existing.scalar_one_or_none():
        verify_dummy_password(payload.password)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        name=payload.name.strip(),
        email=clean_email,
        password_hash=get_password_hash(payload.password),
        role=UserRole.admin,
    )
    db.add(user)
    await db.flush()

    raw_rf, family_id, exp = create_refresh_token(str(user.id))
    rf_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_rf),
        family_id=family_id,
        expires_at=exp,
    )
    db.add(rf_record)
    await db.flush()

    access_token = create_access_token(str(user.id), extra={"role": user.role.value})
    _set_refresh_cookie(response, raw_rf)

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_rf,
    )


@router.post("/login", response_model=TokenResponse)
@rate_limit("5/minute")
async def login(
    request: Request,
    response: Response,
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    clean_email = payload.email.lower().strip()
    result = await db.execute(select(User).where(func.lower(User.email) == clean_email))
    user = result.scalar_one_or_none()

    if not user:
        verify_dummy_password(payload.password)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"Cache-Control": "no-store"},
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"Cache-Control": "no-store"},
        )

    raw_rf, family_id, exp = create_refresh_token(str(user.id))
    rf_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_rf),
        family_id=family_id,
        expires_at=exp,
    )
    db.add(rf_record)
    await db.flush()

    access_token = create_access_token(str(user.id), extra={"role": user.role.value})
    _set_refresh_cookie(response, raw_rf)

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_rf,
    )


@router.post("/refresh", response_model=TokenResponse)
@rate_limit("10/minute")
async def refresh_tokens(
    request: Request,
    response: Response,
    refreshToken: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    raw_token = refreshToken
    if not raw_token:
        auth_hdr = request.headers.get("Authorization")
        if auth_hdr and auth_hdr.startswith("Bearer "):
            raw_token = auth_hdr.replace("Bearer ", "").strip()

    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")

    try:
        payload = decode_token(raw_token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user_id = int(payload["sub"])
    family_id = payload.get("family_id")
    current_hash = hash_token(raw_token)

    res = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == current_hash))
    existing_rf = res.scalar_one_or_none()

    if not existing_rf or existing_rf.is_revoked:
        if family_id:
            await db.execute(
                update(RefreshToken).where(RefreshToken.family_id == family_id).values(is_revoked=True)
            )
            await db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked or reused")

    existing_rf.is_revoked = True

    user_res = await db.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    new_raw_rf, new_family_id, new_exp = create_refresh_token(str(user.id), family_id=family_id)
    new_rf_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_raw_rf),
        family_id=new_family_id,
        expires_at=new_exp,
    )
    db.add(new_rf_record)
    await db.flush()

    new_access_token = create_access_token(str(user.id), extra={"role": user.role.value})
    _set_refresh_cookie(response, new_raw_rf)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_raw_rf,
    )


@router.post("/logout")
async def logout(
    response: Response,
    refreshToken: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if refreshToken:
        current_hash = hash_token(refreshToken)
        res = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == current_hash))
        existing_rf = res.scalar_one_or_none()
        if existing_rf:
            existing_rf.is_revoked = True
            await db.flush()

    _clear_refresh_cookie(response)
    return {"message": "Successfully logged out"}


@router.post("/logout-all")
async def logout_all(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user.id).values(is_revoked=True)
    )
    await db.flush()
    _clear_refresh_cookie(response)
    return {"message": "Logged out from all sessions"}


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user


@router.post("/businesses", response_model=BusinessResponse)
async def create_business(
    payload: BusinessCreate,
    user: User = Depends(require_roles(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
):
    business = Business(user_id=user.id, name=payload.name, currency=payload.currency, timezone=payload.timezone)
    db.add(business)
    await db.flush()
    return business


@router.get("/businesses", response_model=list[BusinessResponse])
async def list_businesses(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Business).where(Business.user_id == user.id).order_by(Business.created_at.desc()))
    return result.scalars().all()
