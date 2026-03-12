"""
AI Sınıflandırma modeli
Claude API'nın ürettiği sınıflandırma sonuçları burada saklanır.
"""

from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy import JSON, String, Numeric, Text, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Classification(Base):
    __tablename__ = "classifications"

    # Bağlı fatura (birebir ilişki)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("invoices.id"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Sınıflandırma sonuçları
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    # low | medium | high
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False
    )  # 0.00 – 1.00

    # Muhasebe önerileri
    suggested_account: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True
    )  # Muhasebe hesap kodu (örn. "6011")
    suggested_payment_method: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )

    # AI analiz notları
    ai_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_model_version: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # Kullanılan Claude model versiyonu

    # Tespit edilen anomaliler (JSON dizisi)
    anomalies: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # Örnek: [{"type": "price_deviation", "severity": "low", "message": "..."}]

    # İlişkiler
    invoice: Mapped["Invoice"] = relationship(  # type: ignore[name-defined]
        "Invoice", back_populates="classification"
    )

    def __repr__(self) -> str:
        return (
            f"<Classification invoice={self.invoice_id} "
            f"category={self.category} risk={self.risk_level} "
            f"confidence={self.confidence_score}>"
        )
