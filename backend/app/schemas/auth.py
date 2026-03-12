"""Auth endpoint şemaları"""

from typing import Optional
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # saniye


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    department: Optional[str] = None

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    status: str = "success"
    data: dict  # TokenResponse + UserOut
