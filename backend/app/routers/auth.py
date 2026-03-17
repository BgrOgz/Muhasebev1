"""
Auth Router
POST /auth/login    → JWT token al
POST /auth/refresh  → Token yenile
POST /auth/logout   → Token geçersiz kıl (client-side)
GET  /auth/me       → Mevcut kullanıcı bilgisi
"""

import time
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from jose import JWTError
from sqlalchemy import select

from app.dependencies import DB, CurrentUser
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, UserOut
from app.utils.exceptions import UnauthorizedError
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.config import settings
from app.utils.logger import logger

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Basit in-memory rate limiter (Redis yoksa) ──────────────────────────────
_login_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 300  # 5 dakika
_RATE_LIMIT_MAX = 5       # 5 deneme / 5 dakika

# ── In-memory token blacklist (logout sonrası token geçersiz kılma) ─────────
_token_blacklist: dict[str, float] = {}  # {jti: expire_timestamp}
_BLACKLIST_CLEANUP_INTERVAL = 300  # Her 5 dakikada süresi dolmuş token'ları temizle
_last_blacklist_cleanup: float = 0.0


def blacklist_token(jti: str, exp_timestamp: float) -> None:
    """Token'ı blacklist'e ekle (logout'ta çağrılır)"""
    global _last_blacklist_cleanup
    _token_blacklist[jti] = exp_timestamp
    # Periyodik temizlik — süresi dolmuş token'ları sil
    now = time.time()
    if now - _last_blacklist_cleanup > _BLACKLIST_CLEANUP_INTERVAL:
        _last_blacklist_cleanup = now
        expired = [k for k, v in _token_blacklist.items() if v < now]
        for k in expired:
            del _token_blacklist[k]


def is_token_blacklisted(jti: str) -> bool:
    """Token blacklist'te mi kontrol et"""
    return jti in _token_blacklist


def _check_rate_limit(key: str) -> bool:
    """Rate limit kontrolü. True = izin verildi, False = bloklandı."""
    now = time.time()
    attempts = _login_attempts[key]
    # Eski denemeleri temizle
    _login_attempts[key] = [t for t in attempts if now - t < _RATE_LIMIT_WINDOW]
    if len(_login_attempts[key]) >= _RATE_LIMIT_MAX:
        return False
    _login_attempts[key].append(now)
    return True


@router.post("/login")
async def login(body: LoginRequest, request: Request, db: DB):
    """Kullanıcı giriş — JWT access + refresh token döner"""

    # Rate limiting — IP bazlı
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        logger.warning(f"[Auth] Rate limit aşıldı: {client_ip}")
        raise UnauthorizedError(
            "Çok fazla giriş denemesi. Lütfen 5 dakika sonra tekrar deneyin."
        )

    result = await db.execute(
        select(User).where(User.email == body.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        logger.warning(f"[Auth] Başarısız giriş denemesi: {body.email} (IP: {client_ip})")
        raise UnauthorizedError("E-posta veya şifre hatalı.")

    # Son giriş zamanını güncelle
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    return {
        "status": "success",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_EXPIRE_HOURS * 3600,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "department": user.department,
            },
        },
    }


@router.post("/refresh")
async def refresh_token(body: RefreshRequest, db: DB):
    """Refresh token ile yeni access token üret"""
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise UnauthorizedError("Geçersiz token türü.")
        user_id = payload.get("sub")
    except JWTError:
        raise UnauthorizedError("Refresh token geçersiz veya süresi dolmuş.")

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedError("Kullanıcı bulunamadı.")

    new_access = create_access_token(str(user.id))
    return {
        "status": "success",
        "data": {
            "access_token": new_access,
            "token_type": "bearer",
            "expires_in": settings.JWT_EXPIRE_HOURS * 3600,
        },
    }


@router.post("/logout")
async def logout(request: Request, current_user: CurrentUser):
    """
    Logout — Token'ı in-memory blacklist'e ekleyerek sunucu tarafında geçersiz kıl.
    """
    # Authorization header'dan token'ı al ve blacklist'e ekle
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = decode_token(token)
            jti = payload.get("jti", "")
            exp = payload.get("exp", 0)
            if jti:
                blacklist_token(jti, exp)
                logger.info(f"[Auth] Token blacklisted: user={current_user.email}")
        except JWTError:
            pass  # Token zaten geçersiz — sorun yok
    return {"status": "success", "message": "Başarıyla çıkış yapıldı."}


@router.get("/me")
async def get_me(current_user: CurrentUser):
    """Mevcut kullanıcının profilini döner"""
    return {
        "status": "success",
        "data": {
            "id": str(current_user.id),
            "email": current_user.email,
            "name": current_user.name,
            "role": current_user.role,
            "department": current_user.department,
            "last_login": current_user.last_login,
        },
    }
