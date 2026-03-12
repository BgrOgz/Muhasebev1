"""
Sistem Router
GET  /system/scheduler-status  → Email scheduler durumu
POST /system/poll-now           → Manuel email taraması tetikle (sadece admin)
GET  /system/email-logs         → Son email işlem logları
"""

from fastapi import APIRouter, Depends

from app.dependencies import DB, CurrentUser, require_role
from app.models.email_log import EmailProcessingLog
from sqlalchemy import select

router = APIRouter(prefix="/system", tags=["Sistem"])


@router.get("/scheduler-status")
async def scheduler_status(current_user: CurrentUser):
    """Email polling scheduler'ın durumunu döndür"""
    from app.services.email_poller import get_scheduler

    scheduler = get_scheduler()
    if not scheduler or not scheduler.running:
        return {"status": "success", "data": {"scheduler": "stopped", "jobs": []}}

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        })

    return {"status": "success", "data": {"scheduler": "running", "jobs": jobs}}


@router.post(
    "/poll-now",
    dependencies=[Depends(require_role("admin"))],
)
async def trigger_poll(current_user: CurrentUser):
    """Manuel email taraması başlat (sadece admin)"""
    from app.services.email_poller import _poll_emails
    import asyncio

    # Background'da çalıştır, sonucu beklemeden döndür
    asyncio.create_task(_poll_emails())

    return {
        "status": "success",
        "message": "Email taraması başlatıldı. Loglardan takip edebilirsiniz.",
    }


@router.get("/email-logs")
async def email_logs(
    current_user: CurrentUser,
    db: DB,
    limit: int = 50,
):
    """Son işlenen email loglarını listele"""
    result = await db.execute(
        select(EmailProcessingLog)
        .order_by(EmailProcessingLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()

    return {
        "status": "success",
        "data": [
            {
                "id": str(log.id),
                "from_email": log.from_email,
                "subject": log.email_subject,
                "filename": log.attachment_filename,
                "status": log.status,
                "error": log.error_message,
                "created_at": log.created_at.isoformat(),
                "processed_at": log.processed_at.isoformat() if log.processed_at else None,
            }
            for log in logs
        ],
    }
