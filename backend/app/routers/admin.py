"""
Admin Router — Sadece admin rolü erişebilir
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GET    /admin/users                → Kullanıcı listesi
POST   /admin/users                → Yeni kullanıcı oluştur
PATCH  /admin/users/{id}           → Kullanıcı güncelle
DELETE /admin/users/{id}           → Soft delete

GET    /admin/suppliers            → Tedarikçi listesi (fatura sayısı + tutar)
GET    /admin/suppliers/{id}       → Tedarikçi detayı
PATCH  /admin/suppliers/{id}       → Tedarikçi güncelle

GET    /admin/audit-logs           → Denetim kayıtları (filtreleme + pagination)
GET    /admin/audit-logs/export    → CSV export
"""

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, case, desc
from sqlalchemy.orm import selectinload

from app.dependencies import DB, CurrentUser, require_role
from app.models.user import User
from app.models.supplier import Supplier
from app.models.invoice import Invoice
from app.models.audit_log import AuditLog
from app.schemas.admin import (
    UserCreateRequest,
    UserUpdateRequest,
    SupplierUpdateRequest,
)
from app.utils.security import hash_password
from app.utils.exceptions import ConflictError, NotFoundError

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_role("admin"))],
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  KULLANICI YÖNETİMİ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/users")
async def list_users(
    current_user: CurrentUser,
    db: DB,
    role: Optional[str] = Query(default=None, description="admin | approver | viewer"),
    is_active: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None, description="İsim veya e-posta ara"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    """Tüm kullanıcıları listele (soft-delete edilenler hariç)"""
    query = select(User).where(User.deleted_at.is_(None))

    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            (User.name.ilike(pattern)) | (User.email.ilike(pattern))
        )

    # Toplam sayı
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Sayfalama
    query = query.order_by(User.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    users = result.scalars().all()

    return {
        "status": "success",
        "data": {
            "items": [
                {
                    "id": str(u.id),
                    "email": u.email,
                    "name": u.name,
                    "role": u.role,
                    "department": u.department,
                    "is_active": u.is_active,
                    "last_login": u.last_login.isoformat() if u.last_login else None,
                    "created_at": u.created_at.isoformat(),
                }
                for u in users
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, -(-total // per_page)),
        },
    }


@router.post("/users", status_code=201)
async def create_user(
    body: UserCreateRequest,
    current_user: CurrentUser,
    db: DB,
):
    """Yeni kullanıcı oluştur"""
    # E-posta benzersizlik kontrolü
    existing = await db.execute(
        select(User).where(User.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"Bu e-posta adresi zaten kayıtlı: {body.email}")

    user = User(
        email=body.email,
        name=body.name,
        password_hash=hash_password(body.password),
        role=body.role,
        department=body.department,
        is_active=True,
    )
    db.add(user)

    # Audit log
    db.add(AuditLog(
        user_id=current_user.id,
        action="admin.user_created",
        resource_type="user",
        new_values={
            "email": body.email,
            "name": body.name,
            "role": body.role,
            "department": body.department,
        },
    ))

    await db.commit()
    await db.refresh(user)

    return {
        "status": "success",
        "data": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "department": user.department,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
        },
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdateRequest,
    current_user: CurrentUser,
    db: DB,
):
    """Kullanıcı bilgilerini güncelle (rol, aktiflik, departman)"""
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("Kullanıcı")

    old_values = {
        "name": user.name,
        "role": user.role,
        "department": user.department,
        "is_active": user.is_active,
    }

    # Güncelle
    if body.name is not None:
        user.name = body.name
    if body.role is not None:
        user.role = body.role
    if body.department is not None:
        user.department = body.department
    if body.is_active is not None:
        user.is_active = body.is_active

    new_values = {
        "name": user.name,
        "role": user.role,
        "department": user.department,
        "is_active": user.is_active,
    }

    # Audit log
    db.add(AuditLog(
        user_id=current_user.id,
        action="admin.user_updated",
        resource_type="user",
        resource_id=user_id,
        old_values=old_values,
        new_values=new_values,
    ))

    await db.commit()
    await db.refresh(user)

    return {
        "status": "success",
        "data": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "department": user.department,
            "is_active": user.is_active,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "created_at": user.created_at.isoformat(),
        },
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    """Kullanıcıyı soft delete yap (geri alınabilir)"""
    # Kendini silemez
    if user_id == current_user.id:
        raise ConflictError("Kendi hesabınızı silemezsiniz.")

    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("Kullanıcı")

    user.deleted_at = datetime.now(timezone.utc)
    user.is_active = False

    # Audit log
    db.add(AuditLog(
        user_id=current_user.id,
        action="admin.user_deleted",
        resource_type="user",
        resource_id=user_id,
        new_values={"email": user.email, "name": user.name, "deleted": True},
    ))

    await db.commit()

    return {"status": "success", "message": f"Kullanıcı silindi: {user.email}"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEDARİKÇİ YÖNETİMİ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/suppliers")
async def list_suppliers(
    current_user: CurrentUser,
    db: DB,
    search: Optional[str] = Query(default=None, description="İsim veya VKN ara"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    """Tedarikçi listesi — fatura sayısı ve toplam tutar ile birlikte"""
    # Subquery: her tedarikçi için fatura istatistikleri
    invoice_stats = (
        select(
            Invoice.supplier_id,
            func.count(Invoice.id).label("invoice_count"),
            func.coalesce(func.sum(Invoice.total_amount), 0).label("total_amount"),
            func.max(Invoice.invoice_date).label("last_invoice_date"),
        )
        .group_by(Invoice.supplier_id)
        .subquery()
    )

    query = (
        select(
            Supplier,
            func.coalesce(invoice_stats.c.invoice_count, 0).label("invoice_count"),
            func.coalesce(invoice_stats.c.total_amount, 0).label("total_amount"),
            invoice_stats.c.last_invoice_date,
        )
        .outerjoin(invoice_stats, Supplier.id == invoice_stats.c.supplier_id)
    )

    if search:
        pattern = f"%{search}%"
        query = query.where(
            (Supplier.name.ilike(pattern)) | (Supplier.vat_number.ilike(pattern))
        )

    # Toplam sayı
    count_q = select(func.count()).select_from(
        select(Supplier.id).where(
            (Supplier.name.ilike(f"%{search}%")) | (Supplier.vat_number.ilike(f"%{search}%"))
        ).subquery()
    ) if search else select(func.count()).select_from(Supplier)
    total = (await db.execute(count_q)).scalar() or 0

    # Sayfalama
    query = query.order_by(desc("total_amount"))
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    rows = result.all()

    return {
        "status": "success",
        "data": {
            "items": [
                {
                    "id": str(supplier.id),
                    "name": supplier.name,
                    "vat_number": supplier.vat_number,
                    "address": supplier.address,
                    "city": supplier.city,
                    "country": supplier.country,
                    "contact_email": supplier.contact_email,
                    "contact_phone": supplier.contact_phone,
                    "invoice_count": inv_count,
                    "total_amount": float(total_amt),
                    "last_invoice_date": str(last_date) if last_date else None,
                    "created_at": supplier.created_at.isoformat(),
                }
                for supplier, inv_count, total_amt, last_date in rows
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, -(-total // per_page)),
        },
    }


@router.get("/suppliers/{supplier_id}")
async def get_supplier(
    supplier_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    """Tedarikçi detayı — son 10 faturası ile birlikte"""
    result = await db.execute(
        select(Supplier).where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise NotFoundError("Tedarikçi")

    # Son faturalar
    invoices_q = (
        select(Invoice)
        .where(Invoice.supplier_id == supplier_id)
        .order_by(Invoice.created_at.desc())
        .limit(10)
    )
    inv_result = await db.execute(invoices_q)
    invoices = inv_result.scalars().all()

    # İstatistikler
    stats_q = select(
        func.count(Invoice.id).label("count"),
        func.coalesce(func.sum(Invoice.total_amount), 0).label("total"),
    ).where(Invoice.supplier_id == supplier_id)
    stats = (await db.execute(stats_q)).one()

    return {
        "status": "success",
        "data": {
            "id": str(supplier.id),
            "name": supplier.name,
            "vat_number": supplier.vat_number,
            "address": supplier.address,
            "city": supplier.city,
            "country": supplier.country,
            "contact_email": supplier.contact_email,
            "contact_phone": supplier.contact_phone,
            "created_at": supplier.created_at.isoformat(),
            "stats": {
                "invoice_count": stats.count,
                "total_amount": float(stats.total),
            },
            "recent_invoices": [
                {
                    "id": str(inv.id),
                    "invoice_number": inv.invoice_number,
                    "invoice_date": str(inv.invoice_date),
                    "total_amount": float(inv.total_amount),
                    "currency": inv.currency,
                    "status": inv.status,
                    "category": inv.category,
                }
                for inv in invoices
            ],
        },
    }


@router.patch("/suppliers/{supplier_id}")
async def update_supplier(
    supplier_id: uuid.UUID,
    body: SupplierUpdateRequest,
    current_user: CurrentUser,
    db: DB,
):
    """Tedarikçi bilgilerini güncelle"""
    result = await db.execute(
        select(Supplier).where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise NotFoundError("Tedarikçi")

    old_values = {}
    new_values = {}
    update_data = body.model_dump(exclude_unset=True)

    # Mass assignment koruması — sadece izin verilen alanlar güncellenebilir
    ALLOWED_SUPPLIER_FIELDS = {"name", "vat_number", "contact_email", "phone", "address", "category", "notes", "is_active"}
    for field, value in update_data.items():
        if field not in ALLOWED_SUPPLIER_FIELDS:
            continue  # İzin verilmeyen alan — atla
        old_val = getattr(supplier, field, None)
        if old_val != value:
            old_values[field] = old_val
            new_values[field] = value
            setattr(supplier, field, value)

    if new_values:
        db.add(AuditLog(
            user_id=current_user.id,
            action="admin.supplier_updated",
            resource_type="supplier",
            resource_id=supplier_id,
            old_values=old_values,
            new_values=new_values,
        ))

    await db.commit()
    await db.refresh(supplier)

    return {
        "status": "success",
        "data": {
            "id": str(supplier.id),
            "name": supplier.name,
            "vat_number": supplier.vat_number,
            "address": supplier.address,
            "city": supplier.city,
            "country": supplier.country,
            "contact_email": supplier.contact_email,
            "contact_phone": supplier.contact_phone,
            "created_at": supplier.created_at.isoformat(),
        },
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DENETİM KAYITLARI (AUDIT LOGS)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/audit-logs")
async def list_audit_logs(
    current_user: CurrentUser,
    db: DB,
    action: Optional[str] = Query(default=None, description="Eylem filtresi (ör: invoice.first_approved)"),
    user_id: Optional[uuid.UUID] = Query(default=None, description="Kullanıcı ID'si"),
    invoice_id: Optional[uuid.UUID] = Query(default=None, description="Fatura ID'si"),
    start_date: Optional[str] = Query(default=None, description="Başlangıç tarihi (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="Bitiş tarihi (YYYY-MM-DD)"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=100),
):
    """Denetim kayıtlarını filtrele ve listele"""
    query = (
        select(AuditLog)
        .options(selectinload(AuditLog.user))
    )

    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if invoice_id:
        query = query.where(AuditLog.invoice_id == invoice_id)
    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
    if end_date:
        query = query.where(AuditLog.created_at <= f"{end_date}T23:59:59")

    # Toplam
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Sayfalama
    query = query.order_by(AuditLog.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "status": "success",
        "data": {
            "items": [
                {
                    "id": str(log.id),
                    "action": log.action,
                    "invoice_id": str(log.invoice_id) if log.invoice_id else None,
                    "user": {
                        "id": str(log.user.id),
                        "name": log.user.name,
                        "email": log.user.email,
                    } if log.user else None,
                    "old_values": log.old_values,
                    "new_values": log.new_values,
                    "status": log.status,
                    "error_message": log.error_message,
                    "ip_address": log.ip_address,
                    "created_at": log.created_at.isoformat(),
                }
                for log in logs
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, -(-total // per_page)),
        },
    }


@router.get("/audit-logs/export")
async def export_audit_logs(
    current_user: CurrentUser,
    db: DB,
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
):
    """Denetim kayıtlarını CSV olarak indir"""
    query = (
        select(AuditLog)
        .options(selectinload(AuditLog.user))
        .order_by(AuditLog.created_at.desc())
    )

    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
    if end_date:
        query = query.where(AuditLog.created_at <= f"{end_date}T23:59:59")

    # Max 10000 kayıt
    query = query.limit(10000)
    result = await db.execute(query)
    logs = result.scalars().all()

    # CSV oluştur
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Tarih", "Kullanıcı", "E-posta", "Eylem",
        "Fatura ID", "Durum", "Hata", "IP Adresi",
    ])

    for log in logs:
        writer.writerow([
            log.created_at.isoformat(),
            log.user.name if log.user else "-",
            log.user.email if log.user else "-",
            log.action,
            str(log.invoice_id) if log.invoice_id else "-",
            log.status,
            log.error_message or "-",
            log.ip_address or "-",
        ])

    output.seek(0)
    filename = f"audit-logs-{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
