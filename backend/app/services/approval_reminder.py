"""
Onay Hatırlatma Servisi
────────────────────────────────────────────────────────────────────────
APScheduler ile her 1 saatte bir çalışır.
AWAITING_FIRST_APPROVAL veya AWAITING_FINAL_APPROVAL durumundaki faturaları
bulur; onaylayanlara hatırlatma e-postası gönderir (max 3 kez).

Hatırlatma sayısı → Classification.anomalies alanında saklanır:
  {"type": "reminder_sent", "count": N, "last_sent": "ISO-timestamp"}
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.approval import Approval, ApprovalLevel, ApprovalStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.classification import Classification
from app.services.notification_service import notification_service
from app.utils.logger import logger

MAX_REMINDERS = 3
REMINDER_INTERVAL_HOURS = 1


async def send_pending_reminders(db: AsyncSession) -> int:
    """
    Bekleyen onaylar için hatırlatma e-postası gönder.
    Gönderilen hatırlatma sayısını döndürür.
    """
    sent_count = 0

    # Bekleyen onayları bul (fatura + sınıflandırma + onaylayan bilgisiyle)
    stmt = (
        select(Approval)
        .where(Approval.status == ApprovalStatus.PENDING)
        .options(
            selectinload(Approval.invoice).selectinload(Invoice.supplier),
            selectinload(Approval.invoice).selectinload(Invoice.classifications),
            selectinload(Approval.approver),
        )
    )
    result = await db.execute(stmt)
    pending_approvals = result.scalars().all()

    for approval in pending_approvals:
        invoice = approval.invoice
        if not invoice:
            continue

        # Sadece doğru statüsteki faturaları işle
        if invoice.status not in (
            InvoiceStatus.AWAITING_FIRST_APPROVAL,
            InvoiceStatus.AWAITING_FINAL_APPROVAL,
        ):
            continue

        # Sınıflandırma bilgisi
        classification = (
            invoice.classifications[0] if invoice.classifications else None
        )

        # Hatırlatma sayacını oku
        reminder_info = _get_reminder_info(classification)
        reminder_count = reminder_info.get("count", 0)

        # Maksimum hatırlatmaya ulaşıldıysa atla
        if reminder_count >= MAX_REMINDERS:
            continue

        # Son gönderimden yeterli süre geçti mi?
        last_sent_str = reminder_info.get("last_sent")
        if last_sent_str:
            try:
                last_sent = datetime.fromisoformat(last_sent_str)
                if datetime.now(timezone.utc) - last_sent < timedelta(
                    hours=REMINDER_INTERVAL_HOURS
                ):
                    continue  # Henüz erken
            except ValueError:
                pass

        # Onaylayan bilgisi
        approver = approval.approver
        if not approver or not approver.email:
            continue

        # Fatura verisini hazırla
        invoice_data = _build_invoice_data(invoice, classification)

        # Hatırlatma gönder
        new_count = reminder_count + 1
        ok = notification_service.notify_approval_reminder(
            approver_email=approver.email,
            invoice_data=invoice_data,
            reminder_count=new_count,
        )

        if ok:
            # Sayacı güncelle
            _update_reminder_info(classification, new_count)
            sent_count += 1
            logger.info(
                f"[Reminder] Hatırlatma #{new_count} gönderildi → "
                f"{approver.email} | {invoice.invoice_number}"
            )

    if sent_count:
        await db.flush()

    return sent_count


# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def _get_reminder_info(classification: Optional[Classification]) -> dict:
    """Classification.anomalies içindeki reminder meta verisini döndür"""
    if not classification or not classification.anomalies:
        return {}
    for item in classification.anomalies:
        if isinstance(item, dict) and item.get("type") == "reminder_meta":
            return item
    return {}


def _update_reminder_info(
    classification: Optional[Classification], new_count: int
) -> None:
    """Classification.anomalies içindeki reminder sayacını güncelle"""
    if not classification:
        return

    anomalies = list(classification.anomalies or [])

    # Varsa eski kaydı kaldır
    anomalies = [
        a for a in anomalies
        if not (isinstance(a, dict) and a.get("type") == "reminder_meta")
    ]

    # Yeni kayıt ekle
    anomalies.append({
        "type": "reminder_meta",
        "count": new_count,
        "last_sent": datetime.now(timezone.utc).isoformat(),
    })

    classification.anomalies = anomalies


def _build_invoice_data(
    invoice: Invoice,
    classification: Optional[Classification],
) -> dict:
    """Bildirim için fatura veri sözlüğü oluştur"""
    return {
        "id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "supplier_name": invoice.supplier.name if invoice.supplier else "Bilinmiyor",
        "total_amount": str(invoice.total_amount),
        "currency": invoice.currency,
        "invoice_date": str(invoice.invoice_date),
        "category": classification.category if classification else invoice.category or "-",
        "risk_level": classification.risk_level if classification else invoice.risk_level or "medium",
        "confidence": float(classification.confidence_score) if classification else 0.0,
        "suggested_account": classification.suggested_account if classification else "-",
        "notes": classification.ai_notes if classification else "",
    }
