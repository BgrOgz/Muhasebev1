"""
Denetim Kaydı (Audit Log) modeli
Tüm işlemler 10 yıl saklanır — Türk vergi mevzuatı gereği.
"""

from typing import Optional
import uuid

from sqlalchemy import JSON, String, Text, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    # Bağlı kaynaklar
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("invoices.id"), nullable=True, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )

    # Olay bilgisi
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Örnek: invoice.created, invoice.classified, invoice.first_approved ...
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )

    # Değişiklik detayları
    old_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # İstek bilgisi
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Sonuç
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="success"
    )  # success | error
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # İlişkiler
    invoice: Mapped[Optional["Invoice"]] = relationship(  # type: ignore[name-defined]
        "Invoice", back_populates="audit_logs"
    )
    user: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]
        "User", back_populates="audit_logs"
    )

    def __repr__(self) -> str:
        return f"<AuditLog action={self.action} status={self.status}>"
