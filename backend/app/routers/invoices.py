"""
Fatura Router
GET    /invoices              → listele (filtreli + sayfalı)
POST   /invoices              → manuel yükle (XML/PDF)
GET    /invoices/{id}         → detay
PATCH  /invoices/{id}         → kategori / not güncelle
DELETE /invoices/{id}         → soft delete (sadece admin)
POST   /invoices/{id}/reclassify → AI ile yeniden sınıflandır
GET    /invoices/{id}/audit-log  → denetim izi
"""

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.dependencies import DB, CurrentUser, require_role
from app.models.invoice import Invoice, InvoiceStatus
from app.models.supplier import Supplier
from app.schemas.invoice import InvoiceFilters, InvoiceUpdateRequest
from app.utils.exceptions import ForbiddenError, NotFoundError, InvalidFileTypeError, FileTooLargeError
from app.config import settings

router = APIRouter(prefix="/invoices", tags=["Faturalar"])


@router.get("")
async def list_invoices(
    current_user: CurrentUser,
    db: DB,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    sort_by: str = Query(default="created_at"),
    order: str = Query(default="desc"),
):
    """Faturaları filtreli ve sayfalı listele"""
    query = (
        select(Invoice)
        .options(selectinload(Invoice.supplier))
        .where(Invoice.deleted_at.is_(None))
    )

    if status:
        query = query.where(Invoice.status == status)
    if category:
        query = query.where(Invoice.category == category)

    # Sıralama — whitelist ile SQL injection önleme
    ALLOWED_SORT_FIELDS = {"created_at", "amount", "total_amount", "invoice_date", "status", "category", "risk_level"}
    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = "created_at"
    sort_col = getattr(Invoice, sort_by, Invoice.created_at)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

    # Toplam kayıt sayısı
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar()

    # Sayfalama
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    invoices = result.scalars().all()

    return {
        "status": "success",
        "data": {
            "items": [_invoice_to_dict(inv) for inv in invoices],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": -(-total // per_page),  # ceiling division
        },
    }


@router.post("", status_code=201)
async def upload_invoice(
    current_user: CurrentUser,
    db: DB,
    file: UploadFile = File(...),
    invoice_type: str = Form(default="ubl-tr"),
):
    """Manuel fatura yükleme (XML veya PDF) — parse eder, DB'ye kaydeder, AI sınıflandırır"""
    from app.services.invoice_processor import InvoiceProcessor
    from app.services.email_service import EmailAttachment

    # Dosya uzantısı kontrolü
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in settings.allowed_extensions_list:
        raise InvalidFileTypeError(settings.allowed_extensions_list)

    # Dosya içeriğini oku
    content = await file.read()

    # Dosya boyutu kontrolü
    if len(content) > settings.max_file_size_bytes:
        raise FileTooLargeError(settings.MAX_FILE_SIZE_MB)

    # Magic bytes ile dosya içeriği doğrulama
    _MAGIC = {
        "pdf": [b"%PDF"],
        "xml": [b"<?xml", b"<Invoice", b"<inv:Invoice"],
        "xls": [b"\xd0\xcf\x11\xe0"],  # OLE2
        "xlsx": [b"PK\x03\x04"],        # ZIP (OOXML)
    }
    signatures = _MAGIC.get(ext, [])
    if signatures and not any(content[:16].lstrip().startswith(sig) for sig in signatures):
        raise InvalidFileTypeError(settings.allowed_extensions_list)

    # EmailAttachment nesnesi oluştur (processor email'den gelen gibi kabul eder)
    attachment = EmailAttachment(
        filename=file.filename or f"upload.{ext}",
        content=content,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
    )

    # InvoiceProcessor ile işle (parse → DB kaydet → AI sınıflandır)
    processor = InvoiceProcessor(db)
    result = await processor.process(
        attachment=attachment,
        from_email=f"manuel_yukle@{current_user.email.split('@')[-1]}",
        email_subject=f"Manuel Yükleme: {file.filename}",
        email_date=None,
        email_id=f"manual_{uuid.uuid4().hex}",
    )

    if not result.get("success"):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=422,
            detail=result.get("error", "Fatura işlenemedi. XML/PDF formatını kontrol edin."),
        )

    await db.commit()

    return {
        "status": "success",
        "data": {
            "invoice_id": result["invoice_id"],
            "filename": file.filename,
            "size_bytes": len(content),
            "message": "Fatura başarıyla yüklendi ve sınıflandırıldı.",
        },
    }


@router.get("/{invoice_id}")
async def get_invoice(invoice_id: uuid.UUID, current_user: CurrentUser, db: DB):
    """Fatura detayını döner (sınıflandırma + onaylar dahil)"""
    result = await db.execute(
        select(Invoice)
        .options(
            selectinload(Invoice.supplier),
            selectinload(Invoice.classification),
            selectinload(Invoice.approvals),
        )
        .where(Invoice.id == invoice_id, Invoice.deleted_at.is_(None))
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise NotFoundError("Fatura")

    return {"status": "success", "data": _invoice_detail_to_dict(invoice)}


@router.patch("/{invoice_id}")
async def update_invoice(
    invoice_id: uuid.UUID,
    body: InvoiceUpdateRequest,
    current_user: CurrentUser,
    db: DB,
):
    """Fatura kategori / not güncelle (approver ve admin yapabilir)"""
    if current_user.role == "viewer":
        raise ForbiddenError("Görüntüleyici fatura güncelleyemez.")

    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.deleted_at.is_(None))
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise NotFoundError("Fatura")

    if body.category is not None:
        invoice.category = body.category
    await db.commit()
    await db.refresh(invoice)

    return {"status": "success", "data": {"id": str(invoice.id), "category": invoice.category}}


@router.delete("/{invoice_id}", dependencies=[Depends(require_role("admin"))])
async def delete_invoice(invoice_id: uuid.UUID, current_user: CurrentUser, db: DB):
    """Hard delete — sadece admin (fatura ve ilişkili kayıtlar tamamen silinir)"""
    from app.models.classification import Classification
    from app.models.approval import Approval
    from app.models.audit_log import AuditLog

    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.deleted_at.is_(None))
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise NotFoundError("Fatura")

    # İlişkili kayıtları sil
    await db.execute(select(AuditLog).where(AuditLog.invoice_id == invoice_id))
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(AuditLog).where(AuditLog.invoice_id == invoice_id))
    await db.execute(sql_delete(Approval).where(Approval.invoice_id == invoice_id))
    await db.execute(sql_delete(Classification).where(Classification.invoice_id == invoice_id))

    # Faturayı tamamen sil
    await db.delete(invoice)
    await db.commit()

    return {"status": "success", "message": "Fatura tamamen silindi."}


@router.post("/{invoice_id}/reclassify")
async def reclassify_invoice(invoice_id: uuid.UUID, current_user: CurrentUser, db: DB):
    """Claude AI ile yeniden sınıflandır (approver ve admin yapabilir)"""
    if current_user.role == "viewer":
        raise ForbiddenError("Görüntüleyici yeniden sınıflandırma yapamaz.")

    from sqlalchemy.orm import selectinload
    from app.services.classification_service import ClassificationService

    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.supplier))
        .where(Invoice.id == invoice_id, Invoice.deleted_at.is_(None))
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise NotFoundError("Fatura")

    svc = ClassificationService(db)
    classification = await svc.classify(invoice)
    await db.commit()

    return {
        "status": "success",
        "data": {
            "invoice_id": str(invoice.id),
            "category": classification.category,
            "risk_level": classification.risk_level,
            "confidence_score": float(classification.confidence_score),
            "suggested_account": classification.suggested_account,
            "ai_notes": classification.ai_notes,
            "anomalies": classification.anomalies,
        },
    }


@router.get("/{invoice_id}/audit-log")
async def get_audit_log(invoice_id: uuid.UUID, current_user: CurrentUser, db: DB):
    """Fatura denetim izini döner"""
    from app.models.audit_log import AuditLog

    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.invoice_id == invoice_id)
        .order_by(AuditLog.created_at.asc())
    )
    logs = result.scalars().all()

    return {
        "status": "success",
        "data": [
            {
                "id": str(log.id),
                "action": log.action,
                "status": log.status,
                "old_values": log.old_values,
                "new_values": log.new_values,
                "timestamp": log.created_at,
            }
            for log in logs
        ],
    }


# ── Yardımcı dönüşüm fonksiyonları ───────────────────────────────────────────

def _invoice_to_dict(inv: Invoice) -> dict:
    return {
        "id": str(inv.id),
        "invoice_number": inv.invoice_number,
        "supplier": {
            "id": str(inv.supplier.id),
            "name": inv.supplier.name,
            "vat_number": inv.supplier.vat_number,
        } if inv.supplier else None,
        "amount": float(inv.amount),
        "tax_amount": float(inv.tax_amount),
        "total_amount": float(inv.total_amount),
        "currency": inv.currency,
        "invoice_date": str(inv.invoice_date),
        "due_date": str(inv.due_date) if inv.due_date else None,
        "status": inv.status,
        "category": inv.category,
        "risk_level": inv.risk_level,
        "created_at": inv.created_at.isoformat(),
    }


def _invoice_detail_to_dict(inv: Invoice) -> dict:
    base = _invoice_to_dict(inv)
    base["classification"] = (
        {
            "id": str(inv.classification.id),
            "category": inv.classification.category,
            "risk_level": inv.classification.risk_level,
            "confidence_score": float(inv.classification.confidence_score),
            "suggested_account": inv.classification.suggested_account,
            "ai_notes": inv.classification.ai_notes,
            "anomalies": inv.classification.anomalies,
            "ai_model_version": inv.classification.ai_model_version,
        }
        if inv.classification
        else None
    )
    base["approvals"] = [
        {
            "id": str(a.id),
            "approval_level": a.approval_level,
            "status": a.status,
            "comments": a.comments,
            "approved_at": a.approved_at.isoformat() if a.approved_at else None,
        }
        for a in inv.approvals
    ]
    base["source_email"] = inv.source_email
    base["source_filename"] = inv.source_filename
    return base
