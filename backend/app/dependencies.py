"""
FastAPI Dependency Injection
- get_db       → veritabanı session
- get_current_user  → JWT'den aktif kullanıcı
- require_role      → rol bazlı erişim kontrolü
"""

import uuid
from typing import Annotated, Optional

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.utils.exceptions import ForbiddenError, UnauthorizedError
from app.utils.security import decode_token

# Bearer token scheme
_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Authorization header'dan JWT çöz, kullanıcıyı döndür.
    Token eksik veya geçersizse 401 fırlatır.
    """
    if not credentials:
        raise UnauthorizedError("Authorization header eksik.")

    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if not user_id:
            raise UnauthorizedError("Geçersiz token: 'sub' alanı yok.")
    except JWTError:
        raise UnauthorizedError("Token geçersiz veya süresi dolmuş.")

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id), User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedError("Kullanıcı bulunamadı veya hesap devre dışı.")

    return user


# Tip kısayolları — router'larda kolayca kullanmak için
CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]


def require_role(*roles: str):
    """
    Belirli rollere erişimi kısıtlayan dependency factory.

    Kullanım:
        @router.delete("/invoices/{id}", dependencies=[Depends(require_role("admin"))])
    """
    async def _check(current_user: CurrentUser):
        if current_user.role not in roles:
            raise ForbiddenError(
                f"Bu işlem için gerekli rol: {', '.join(roles)}. "
                f"Sizin rolünüz: {current_user.role}"
            )
        return current_user

    return _check
