"""
Email İşlem Kaydı modeli
Gmail'den gelen her e-posta için işlem durumu takibi.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class EmailProcessingLog(Base):
    __tablename__ = "email_processing_logs"

    # Email kimliği (Gmail message ID)
    email_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Gönderen
    from_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email_subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Ek dosya bilgisi
    attachment_filename: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # İşlem durumu
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="received", index=True
    )
    # received | processing | success | failed | skipped

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Zaman damgaları
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<EmailLog from={self.from_email} "
            f"file={self.attachment_filename} status={self.status}>"
        )
