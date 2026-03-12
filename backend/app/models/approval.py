"""
Onay (Approval) modeli
İki aşamalı onay: first (muhasebeci) → final (patron)
"""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import String, Text, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ApprovalLevel:
    FIRST = "first"   # Birinci onaylayan (muhasebeci)
    FINAL = "final"   # Son onaylayan (patron)


class ApprovalStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Approval(Base):
    __tablename__ = "approvals"

    # Bağlı fatura
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Onaylayan kullanıcı
    approver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Onay detayları
    approval_level: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # first | final
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ApprovalStatus.PENDING, index=True
    )

    # Karar bilgileri
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason_rejected: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Onay zaman damgası
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # İstek metadata
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # İlişkiler
    invoice: Mapped["Invoice"] = relationship(  # type: ignore[name-defined]
        "Invoice", back_populates="approvals"
    )
    approver: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]
        "User", back_populates="approvals", foreign_keys=[approver_id]
    )

    def __repr__(self) -> str:
        return (
            f"<Approval invoice={self.invoice_id} "
            f"level={self.approval_level} status={self.status}>"
        )
