"""Admin panel endpoint şemaları"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator


# ── Kullanıcı Yönetimi ─────────────────────────────────────────────────────

class UserCreateRequest(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str = "viewer"
    department: Optional[str] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = ("admin", "approver", "viewer")
        if v not in allowed:
            raise ValueError(f"Geçersiz rol. İzin verilenler: {', '.join(allowed)}")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Şifre en az 8 karakter olmalıdır")
        return v


class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            allowed = ("admin", "approver", "viewer")
            if v not in allowed:
                raise ValueError(f"Geçersiz rol. İzin verilenler: {', '.join(allowed)}")
        return v


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    role: str
    department: Optional[str] = None
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Tedarikçi Yönetimi ─────────────────────────────────────────────────────

class SupplierUpdateRequest(BaseModel):
    name: Optional[str] = None
    vat_number: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class SupplierResponse(BaseModel):
    id: UUID
    name: str
    vat_number: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    invoice_count: int = 0
    total_amount: float = 0.0
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Audit Log ──────────────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: UUID
    action: str
    invoice_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    old_values: Optional[dict] = None
    new_values: Optional[dict] = None
    status: str
    error_message: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
