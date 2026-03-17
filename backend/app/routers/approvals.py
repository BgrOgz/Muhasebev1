"""
Onay Router
GET   /approvals              → bekleyen onaylarımı listele
PATCH /approvals/{id}         → onayla veya reddet
GET   /invoices/{id}/approvals → fatura onay geçmişi
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import DB, CurrentUser
from app.models.approval import Approval, ApprovalLevel, ApprovalStatus
from app.models.classification import Classification
from app.models.invoice import Invoice, InvoiceStatus
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.approval import ApprovalActionRequest
from app.services.notification_service import notification_service
from app.utils.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.utils.logger import logger

router = APIRouter(prefix="/approvals", tags=["Onaylar"])


@router.get("")
async def list_my_approvals(
    current_user: CurrentUser,
    db: DB,
    approval_level: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default="pending"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    """Onayları listele.
    - admin: tüm onayları görür
    - approver: tüm onayları görür (sadece low/medium risk işleyebilir)
    - diğer roller: sadece kendine atananları görür"""

    # Onay kaydı eksik olan faturaları otomatik düzelt (admin/approver için)
    if current_user.role in ("admin", "approver"):
        await _auto_create_missing_approvals(db, current_user)

    query = (
        select(Approval)
        .options(selectinload(Approval.invoice).selectinload(Invoice.supplier))
    )
    # Admin ve approver tüm onayları görür, diğer roller sadece kendine atananları
    if current_user.role not in ("admin", "approver"):
        query = query.where(Approval.approver_id == current_user.id)

    if status:
        query = query.where(Approval.status == status)
    if approval_level:
        query = query.where(Approval.approval_level == approval_level)

    query = query.order_by(Approval.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    approvals = result.scalars().all()

    # Approver yüksek risk işleyemez — can_action bilgisi ekle
    def _can_action(approval_item) -> bool:
        if current_user.role == "admin":
            return True
        if current_user.role == "approver":
            risk = approval_item.invoice.risk_level if approval_item.invoice else "medium"
            return risk != "high"
        # Diğer roller — sadece kendine atananları işleyebilir
        return approval_item.approver_id == current_user.id

    return {
        "status": "success",
        "data": {
            "items": [
                {
                    "id": str(a.id),
                    "invoice": {
                        "id": str(a.invoice.id),
                        "invoice_number": a.invoice.invoice_number,
                        "supplier": a.invoice.supplier.name if a.invoice.supplier else "-",
                        "amount": float(a.invoice.total_amount),
                        "status": a.invoice.status,
                        "category": a.invoice.category,
                        "risk_level": a.invoice.risk_level,
                    },
                    "approval_level": a.approval_level,
                    "status": a.status,
                    "can_action": _can_action(a),
                    "created_at": a.created_at.isoformat(),
                }
                for a in approvals
            ],
        },
    }


@router.patch("/{approval_id}")
async def action_approval(
    approval_id: uuid.UUID,
    body: ApprovalActionRequest,
    current_user: CurrentUser,
    db: DB,
):
    """Faturayı onayla veya reddet — workflow durumunu otomatik ilerletir"""

    # Onay kaydını + ilgili fatura, tedarikçi ve sınıflandırmayla getir
    result = await db.execute(
        select(Approval)
        .options(
            selectinload(Approval.invoice).selectinload(Invoice.supplier),
            selectinload(Approval.invoice).selectinload(Invoice.classification),
        )
        .where(Approval.id == approval_id)
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise NotFoundError("Onay kaydı")

    # Yetki kontrolü:
    # - admin: tüm onayları işleyebilir
    # - approver: sadece low/medium risk onayları işleyebilir
    # - diğer: sadece kendine atananları
    if approval.approver_id != current_user.id:
        if current_user.role == "admin":
            pass  # Admin her şeyi işleyebilir
        elif current_user.role == "approver":
            invoice_risk = approval.invoice.risk_level if approval.invoice else "medium"
            if invoice_risk == "high":
                raise ForbiddenError(
                    "Yüksek riskli faturalar sadece admin tarafından onaylanabilir."
                )
        else:
            raise ForbiddenError("Bu onay size ait değil.")
    elif current_user.role == "approver":
        # Kendine atanmış olsa bile high risk kontrolü
        invoice_risk = approval.invoice.risk_level if approval.invoice else "medium"
        if invoice_risk == "high":
            raise ForbiddenError(
                "Yüksek riskli faturalar sadece admin tarafından onaylanabilir."
            )

    # Zaten işlem yapılmış mı?
    if approval.status != ApprovalStatus.PENDING:
        raise ValidationError("Bu onay zaten işlem görmüş.")

    # Durum geçişi doğrula
    if body.status not in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
        raise ValidationError("Geçersiz durum. 'approved' veya 'rejected' girin.")

    approval.status = body.status
    approval.comments = body.comments
    approval.reason_rejected = body.reason_rejected
    approval.approved_at = datetime.now(timezone.utc)

    invoice = approval.invoice
    classification = (
        invoice.classification
    )
    next_step = None
    notifications_sent: list[str] = []

    # ── Fatura veri paketi (bildirimler için) ────────────────────────────────
    invoice_data = _build_invoice_data(invoice, classification)

    # ── Workflow geçişi + bildirimler ─────────────────────────────────────────
    if body.status == ApprovalStatus.APPROVED:

        if approval.approval_level == ApprovalLevel.FIRST:
            # 1. onay verildi → patron onayına gönder
            invoice.status = InvoiceStatus.AWAITING_FINAL_APPROVAL
            next_step = "Patron onayına gönderildi"

            # Nihai onaylayan için Approval kaydı oluştur
            final_approver = await _get_user_by_email(
                db, _get_setting("FINAL_APPROVER_EMAIL")
            )
            if final_approver:
                db.add(Approval(
                    invoice_id=invoice.id,
                    approver_id=final_approver.id,
                    approval_level=ApprovalLevel.FINAL,
                    status=ApprovalStatus.PENDING,
                ))

                # Patron'a bildirim
                notification_service.notify_first_approved(
                    final_approver_email=final_approver.email,
                    invoice_data=invoice_data,
                    first_approver_name=current_user.name or current_user.email,
                    notes=body.comments,
                )
                notifications_sent.append(final_approver.email)

        elif approval.approval_level == ApprovalLevel.FINAL:
            # Patron onayladı → arşivle
            invoice.status = InvoiceStatus.APPROVED
            next_step = "Fatura onaylandı — muhasebe kaydı oluşturulacak"

            # Muhasebe + birinci onaylayan bildirim
            recipients = _collect_recipients(
                _get_setting("FIRST_APPROVER_EMAIL"),
                _get_setting("NOTIFICATION_CC_EMAIL"),
            )
            notification_service.notify_final_approved(
                recipients=recipients,
                invoice_data=invoice_data,
                approver_name=current_user.name or current_user.email,
                notes=body.comments,
            )
            notifications_sent.extend(recipients)

    elif body.status == ApprovalStatus.REJECTED:

        if approval.approval_level == ApprovalLevel.FIRST:
            # Birinci onaylayan reddetti → fatura iade edildi
            invoice.status = InvoiceStatus.RETURNED
            next_step = "Fatura birinci onayda reddedildi — iade"

            recipients = _collect_recipients(
                _get_setting("FINAL_APPROVER_EMAIL"),
                _get_setting("NOTIFICATION_CC_EMAIL"),
            )
            notification_service.notify_first_rejected(
                recipients=recipients,
                invoice_data=invoice_data,
                rejector_name=current_user.name or current_user.email,
                rejection_notes=body.reason_rejected,
            )
            notifications_sent.extend(recipients)

        elif approval.approval_level == ApprovalLevel.FINAL:
            # Patron reddetti → kesin red
            invoice.status = InvoiceStatus.REJECTED
            next_step = "Fatura kesin olarak reddedildi"

            recipients = _collect_recipients(
                _get_setting("FIRST_APPROVER_EMAIL"),
                _get_setting("NOTIFICATION_CC_EMAIL"),
            )
            notification_service.notify_final_rejected(
                recipients=recipients,
                invoice_data=invoice_data,
                rejector_name=current_user.name or current_user.email,
                rejection_notes=body.reason_rejected,
            )
            notifications_sent.extend(recipients)

    # ── Audit log kaydet ──────────────────────────────────────────────────────
    action_key = (
        f"invoice.{approval.approval_level}_"
        f"{'approved' if body.status == ApprovalStatus.APPROVED else 'rejected'}"
    )
    db.add(
        AuditLog(
            invoice_id=invoice.id,
            user_id=current_user.id,
            action=action_key,
            new_values={
                "status": body.status,
                "comments": body.comments,
                "reason_rejected": body.reason_rejected,
                "approver": current_user.name or current_user.email,
                "notifications_sent": notifications_sent,
            },
        )
    )

    await db.commit()

    return {
        "status": "success",
        "data": {
            "id": str(approval.id),
            "invoice_id": str(invoice.id),
            "approval_level": approval.approval_level,
            "status": approval.status,
            "comments": approval.comments,
            "approved_at": approval.approved_at.isoformat(),
            "next_step": next_step,
            "notifications_sent": notifications_sent,
        },
    }


# ── Eksik onay kayıtlarını otomatik oluştur ──────────────────────────────────

async def _auto_create_missing_approvals(db, current_user) -> None:
    """
    awaiting_first_approval veya awaiting_final_approval durumundaki faturalar
    için Approval kaydı yoksa otomatik oluştur.
    Bu durumlar, fatura yüklendiğinde FIRST_APPROVER_EMAIL ile eşleşen kullanıcı
    bulunamadığında ortaya çıkar.
    """
    from sqlalchemy import and_, exists

    # 1. awaiting_first_approval durumunda olup pending first-approval kaydı olmayan faturalar
    first_subq = (
        select(Approval.invoice_id)
        .where(
            Approval.approval_level == ApprovalLevel.FIRST,
            Approval.status == ApprovalStatus.PENDING,
        )
    )
    missing_first = await db.execute(
        select(Invoice)
        .where(
            Invoice.status == InvoiceStatus.AWAITING_FIRST_APPROVAL,
            ~Invoice.id.in_(first_subq),
        )
    )
    invoices_needing_first = missing_first.scalars().all()

    # 2. awaiting_final_approval durumunda olup pending final-approval kaydı olmayan faturalar
    final_subq = (
        select(Approval.invoice_id)
        .where(
            Approval.approval_level == ApprovalLevel.FINAL,
            Approval.status == ApprovalStatus.PENDING,
        )
    )
    missing_final = await db.execute(
        select(Invoice)
        .where(
            Invoice.status == InvoiceStatus.AWAITING_FINAL_APPROVAL,
            ~Invoice.id.in_(final_subq),
        )
    )
    invoices_needing_final = missing_final.scalars().all()

    created = 0

    for inv in invoices_needing_first:
        # Uygun approver bul: önce config'deki email, sonra herhangi bir admin
        approver = await _get_user_by_email(db, _get_setting("FIRST_APPROVER_EMAIL"))
        if not approver:
            result = await db.execute(
                select(User).where(User.role == "admin", User.is_active == True).limit(1)
            )
            approver = result.scalar_one_or_none()
        if approver:
            db.add(Approval(
                invoice_id=inv.id,
                approver_id=approver.id,
                approval_level=ApprovalLevel.FIRST,
                status=ApprovalStatus.PENDING,
            ))
            created += 1

    for inv in invoices_needing_final:
        approver = await _get_user_by_email(db, _get_setting("FINAL_APPROVER_EMAIL"))
        if not approver:
            result = await db.execute(
                select(User).where(User.role == "admin", User.is_active == True).limit(1)
            )
            approver = result.scalar_one_or_none()
        if approver:
            db.add(Approval(
                invoice_id=inv.id,
                approver_id=approver.id,
                approval_level=ApprovalLevel.FINAL,
                status=ApprovalStatus.PENDING,
            ))
            created += 1

    if created:
        await db.flush()
        logger.info(f"[Approvals] {created} eksik onay kaydı otomatik oluşturuldu")


# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def _get_setting(key: str) -> str:
    from app.config import settings
    return getattr(settings, key, "")


def _collect_recipients(*emails: str) -> list[str]:
    """Boş ve tekrarlı olmayan e-posta listesi döndür"""
    seen: set[str] = set()
    result: list[str] = []
    for e in emails:
        if e and e not in seen:
            seen.add(e)
            result.append(e)
    return result


async def _get_user_by_email(db, email: str):
    """E-posta adresine göre aktif kullanıcıyı bul"""
    if not email:
        return None
    from app.models.user import User
    result = await db.execute(
        select(User).where(User.email == email, User.is_active == True)
    )
    return result.scalar_one_or_none()


def _build_invoice_data(invoice: Invoice, classification) -> dict:
    """Bildirim için fatura veri sözlüğü"""
    return {
        "id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "supplier_name": invoice.supplier.name if invoice.supplier else "Bilinmiyor",
        "total_amount": str(invoice.total_amount),
        "currency": invoice.currency,
        "invoice_date": str(invoice.invoice_date),
        "category": (
            classification.category if classification else invoice.category or "-"
        ),
        "risk_level": (
            classification.risk_level
            if classification
            else invoice.risk_level or "medium"
        ),
        "confidence": (
            float(classification.confidence_score) if classification else 0.0
        ),
        "suggested_account": (
            classification.suggested_account if classification else "-"
        ),
        "notes": (
            classification.ai_notes if classification else ""
        ),
    }
