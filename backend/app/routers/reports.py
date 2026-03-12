"""
Rapor Router
GET /reports/summary    → aylık özet
GET /reports/categories → kategori analizi
GET /reports/export     → CSV/Excel export
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.dependencies import DB, CurrentUser
from app.models.classification import Classification
from app.models.invoice import Invoice
from app.models.supplier import Supplier

router = APIRouter(prefix="/reports", tags=["Raporlar"])


@router.get("/summary")
async def summary_report(
    current_user: CurrentUser,
    db: DB,
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
):
    """Belirli tarih aralığında fatura özeti"""
    # Varsayılan: son 30 gün
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    # Temel istatistikler
    stats_result = await db.execute(
        select(
            func.count(Invoice.id).label("total"),
            func.sum(Invoice.total_amount).label("total_amount"),
            func.sum(Invoice.tax_amount).label("total_tax"),
        ).where(
            Invoice.invoice_date.between(start_date, end_date),
            Invoice.deleted_at.is_(None),
        )
    )
    stats = stats_result.one()

    # Durum dağılımı
    status_result = await db.execute(
        select(Invoice.status, func.count(Invoice.id)).where(
            Invoice.invoice_date.between(start_date, end_date),
            Invoice.deleted_at.is_(None),
        ).group_by(Invoice.status)
    )
    by_status = dict(status_result.all())

    # Kategori bazlı
    cat_result = await db.execute(
        select(
            Invoice.category,
            func.count(Invoice.id).label("count"),
            func.sum(Invoice.total_amount).label("amount"),
        ).where(
            Invoice.invoice_date.between(start_date, end_date),
            Invoice.deleted_at.is_(None),
            Invoice.category.isnot(None),
        ).group_by(Invoice.category)
        .order_by(func.sum(Invoice.total_amount).desc())
    )
    by_category = cat_result.all()
    total_amount = float(stats.total_amount or 0)

    # Tedarikçi bazlı
    sup_result = await db.execute(
        select(
            Supplier.name,
            func.count(Invoice.id).label("count"),
            func.sum(Invoice.total_amount).label("amount"),
        )
        .join(Invoice, Invoice.supplier_id == Supplier.id)
        .where(
            Invoice.invoice_date.between(start_date, end_date),
            Invoice.deleted_at.is_(None),
        )
        .group_by(Supplier.name)
        .order_by(func.sum(Invoice.total_amount).desc())
        .limit(10)
    )
    by_supplier = sup_result.all()

    # Risk dağılımı (classification tablosundan)
    risk_result = await db.execute(
        select(
            Classification.risk_level,
            func.count(Classification.id).label("count"),
        )
        .join(Invoice, Invoice.id == Classification.invoice_id)
        .where(
            Invoice.invoice_date.between(start_date, end_date),
            Invoice.deleted_at.is_(None),
        )
        .group_by(Classification.risk_level)
    )
    by_risk = risk_result.all()

    # Ortalama güven skoru
    conf_result = await db.execute(
        select(func.avg(Classification.confidence_score))
        .join(Invoice, Invoice.id == Classification.invoice_id)
        .where(
            Invoice.invoice_date.between(start_date, end_date),
            Invoice.deleted_at.is_(None),
        )
    )
    avg_confidence = float(conf_result.scalar() or 0)

    return {
        "status": "success",
        "data": {
            "period": {"start": str(start_date), "end": str(end_date)},
            "total_invoices": stats.total or 0,
            "total_amount": total_amount,
            "total_tax": float(stats.total_tax or 0),
            "approved_count": by_status.get("approved", 0),
            "pending_count": (
                by_status.get("awaiting_first_approval", 0)
                + by_status.get("awaiting_final_approval", 0)
            ),
            "rejected_count": by_status.get("rejected", 0),
            "avg_confidence": avg_confidence,
            "by_category": [
                {
                    "category": row.category,
                    "count": row.count,
                    "total_amount": float(row.amount),
                    "percentage": round(
                        float(row.amount) / total_amount * 100, 1
                    ) if total_amount else 0,
                }
                for row in by_category
            ],
            "by_supplier": [
                {
                    "supplier_name": row.name,
                    "invoice_count": row.count,
                    "total_amount": float(row.amount),
                }
                for row in by_supplier
            ],
            "by_risk": [
                {"level": row.risk_level, "count": row.count}
                for row in by_risk
            ],
        },
    }


@router.get("/categories")
async def category_analysis(current_user: CurrentUser, db: DB):
    """Tüm kategorilerin istatistiksel dağılımı"""
    result = await db.execute(
        select(
            Invoice.category,
            func.count(Invoice.id).label("count"),
            func.sum(Invoice.total_amount).label("total"),
            func.avg(Invoice.total_amount).label("avg"),
        )
        .where(Invoice.deleted_at.is_(None), Invoice.category.isnot(None))
        .group_by(Invoice.category)
        .order_by(func.count(Invoice.id).desc())
    )
    rows = result.all()

    return {
        "status": "success",
        "data": [
            {
                "category": r.category,
                "count": r.count,
                "total_amount": float(r.total or 0),
                "avg_amount": float(r.avg or 0),
            }
            for r in rows
        ],
    }


@router.get("/export")
async def export_report(
    current_user: CurrentUser,
    db: DB,
    format: str = Query(default="csv", pattern="^(csv|excel)$"),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
):
    """Faturaları CSV veya Excel olarak dışa aktar"""
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=365)
    import csv
    import io

    result = await db.execute(
        select(Invoice)
        .where(
            Invoice.invoice_date.between(start_date, end_date),
            Invoice.deleted_at.is_(None),
        )
        .order_by(Invoice.invoice_date.desc())
    )
    invoices = result.scalars().all()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["Fatura No", "Tarih", "Tutar", "KDV", "Toplam", "Durum", "Kategori"]
        )
        for inv in invoices:
            writer.writerow([
                inv.invoice_number,
                inv.invoice_date,
                inv.amount,
                inv.tax_amount,
                inv.total_amount,
                inv.status,
                inv.category or "-",
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=faturalar_{start_date}_{end_date}.csv"
            },
        )

    return {"status": "error", "message": "Excel export yakında eklenecek."}
