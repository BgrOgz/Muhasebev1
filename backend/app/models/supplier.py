"""
Tedarikçi (Supplier) modeli
Fatura gönderen firmalar burada saklanır.
"""

from typing import Optional, List

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    vat_number: Mapped[Optional[str]] = mapped_column(
        String(20), unique=True, nullable=True, index=True
    )  # Vergi numarası
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="Turkey")
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # İlişkiler
    invoices: Mapped[List["Invoice"]] = relationship(  # type: ignore[name-defined]
        "Invoice", back_populates="supplier"
    )

    def __repr__(self) -> str:
        return f"<Supplier {self.name} ({self.vat_number})>"
