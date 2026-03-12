"""
Kullanıcı modeli
Roller: admin | approver | viewer
"""

from datetime import datetime
from typing import Optional, List
import uuid

from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class User(Base):
    __tablename__ = "users"

    # Kimlik bilgileri
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Rol ve durum
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="viewer", index=True
    )
    # Geçerli roller: admin, approver, viewer
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Zaman damgaları
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # İlişkiler
    approvals: Mapped[List["Approval"]] = relationship(  # type: ignore[name-defined]
        "Approval", back_populates="approver", foreign_keys="Approval.approver_id"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(  # type: ignore[name-defined]
        "AuditLog", back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"
