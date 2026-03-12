"""
Fatura (Invoice) modeli
Sistemin kalbi — tüm e-fatura verileri burada.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
import uuid

from sqlalchemy import JSON, String, Numeric, Date, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


# Fatura durum sabitleri
class InvoiceStatus:
    DRAFT = "draft"                                 # Taslak
    PROCESSING = "processing"                       # AI işliyor
    AWAITING_FIRST_APPROVAL = "awaiting_first_approval"   # 1. onay bekliyor
    RETURNED = "returned"                           # İade edildi
    AWAITING_FINAL_APPROVAL = "awaiting_final_approval"   # Patron onayı bekliyor
    APPROVED = "approved"                           # Onaylandı
    REJECTED = "rejected"                           # Reddedildi
    ARCHIVED = "archived"                           # Arşivlendi (muhasebe kaydı OK)


class Invoice(Base):
    __tablename__ = "invoices"

    # Fatura kimliği
    invoice_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )

    # Tedarikçi bağlantısı
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("suppliers.id"),
        nullable=False,
        index=True,
    )

    # Tutarlar
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")

    # Tarihler
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Durum ve sınıflandırma
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=InvoiceStatus.DRAFT,
        index=True,
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    risk_level: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # low | medium | high

    # UBL-TR XML içeriği (tam belge JSON olarak)
    ubl_xml: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Email kaynağı bilgileri
    source_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_email_subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Soft delete
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # İlişkiler
    supplier: Mapped["Supplier"] = relationship(  # type: ignore[name-defined]
        "Supplier", back_populates="invoices"
    )
    classification: Mapped[Optional["Classification"]] = relationship(  # type: ignore[name-defined]
        "Classification", back_populates="invoice", uselist=False
    )
    approvals: Mapped[List["Approval"]] = relationship(  # type: ignore[name-defined]
        "Approval", back_populates="invoice", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(  # type: ignore[name-defined]
        "AuditLog", back_populates="invoice"
    )

    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_number} ({self.status})>"
