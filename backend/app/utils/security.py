"""
Güvenlik yardımcıları
- Parola hash/verify
- JWT token üretimi ve doğrulaması
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# Bcrypt context — parola hashleme için
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Parola ────────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Düz metni bcrypt ile hashle"""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Düz metin ile hash eşleşiyor mu?"""
    return _pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(subject: Any, expires_delta: Optional[timedelta] = None) -> str:
    """
    JWT access token üret.
    subject: genellikle user UUID veya email
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=settings.JWT_EXPIRE_HOURS)
    )
    payload = {"sub": str(subject), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: Any) -> str:
    """JWT refresh token üret (7 günlük)"""
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    payload = {"sub": str(subject), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """
    JWT token çöz.
    Geçersiz veya süresi dolmuşsa JWTError fırlatır.
    """
    return jwt.decode(
        token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )
